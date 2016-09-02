import sys
sys.path.append('../')
from common import *

def connect_to_apic(host, user_id, password, secure):
	# Connect to the APIC and return MODirectory
	controllerUrl = 'https://' + host

	login_session = LoginSession(controllerUrl, user_id, password, secure)
	modir = MoDirectory(login_session)
	modir.login()
	return modir
def commit_mo(mo_directory, mo, retries=5):
	"""
	Commit a managed object using the underlying cobra call.
	Adds a small layer of reliability over the top to attempt retries
	"""
	for attempt in range(retries):
		try:
			c = cobra.mit.request.ConfigRequest()
			c.addMo(mo)
			mo_directory.commit(c)
			return
		except (HTTPException, CommitError) as e:
			print e
			print 'Caught a exception trying to commit MO'
			print 'This was attempt {}'.format(attempt + 1)
			print 'Sleeping for 30 seconds to relieve pressure on APIC'
			sleep(30)
		except ValueError as e:
			print 'Maximum request size exceeded!'
			print 'The APIC has a hard limit of 1MB per POST request'
			print 'Unfortunately when creating MOs at scale this can easily be hit'
			print 'I have spoken with engineering but in FCS this limit is set'
			print 'Try reducing the number of objects you are creating at one time (a common culprit is many paths per EPG)'
			print ''
			print 'Exiting'
			sys.exit(1)
	else:
		raise CommitException('Could not commit MO')

def Create_PG_VPC_NAME(site,Node_ID,Port):
	return 'leaf{}-{}-{}-pg'.format(Node_ID,int(Node_ID)+1,Port)

def isinrange(vlan_id,str):
	if str !=None:
		mystr=str.split(',')
		for i in range (0,len(mystr)):
			str1=mystr[i]
			if str1.find("-") == -1:
				if vlan_id == int(str1):
					return True
				elif vlan_id < int(str1):
					return False
			else:
				str2=str1.split('-')
				if vlan_id>=int(str2[0]) and vlan_id<=int(str2[1]):
					return True
				elif vlan_id <int(str2[0]):
					return False
		return False
				
def create_cp(md, site,brownfield, excel_file, config_file, mynode_id):
	"""
	Create tenant_count * bd_count BDs
	The tenant and application profile will be made if not present
	The naming scheme is always tenant-<unique_id>-<mo>-<count>
	"""
	# log into the APIC and create a directory object
	# Assuming every tenant will have a single app profile, 3x epgs app/web/db etc..
	# and single private network and 3 bds , one per each epg
	t1 = time.time()	
	for tenant_id in range(1,2):
		config = ConfigParser.ConfigParser()
		config.read(config_file)
		dhcp_server = config.get("myvars", "dhcp_server")
		L3_NODE_ID= config.get("L3_OUT", "NODE_ID")
                l3_dom= config.get("myvars", "L3_DOM")
		mynode_id = int(mynode_id)		
		t2 = time.time()
		tenant_name = '{}-cp'.format(site)
		wb = load_workbook(excel_file,data_only=True)
		print 'Creating Tenant', tenant_name
		# the top level object on which operations will be made
		# Create the tenant, private network/vrf/context, and security domain
		VRF_NO=int(config.get("myvars", "CP_VRF_NO"))
                vpod_cp=config.get("myvars", "VPOD_CP")
		VPC_INT=int(config.get("L3_OUT", "VPC_INT_NO"))
		dhcp_l3out=config.get("myvars", "dhcp_l3out_name")
		topMo = cobra.model.pol.Uni('')
		fvTenant = cobra.model.fv.Tenant(topMo, name=tenant_name)
		if (int(brownfield) == 1 and mynode_id==301) or int(brownfield) == 0:
			aaaDomainRef = cobra.model.aaa.DomainRef(fvTenant, name='{}-sec-domain'.format(site))			
			dhcpRelayP = cobra.model.dhcp.RelayP(fvTenant, ownerKey='', name='{}-dhcp-relay'.format(site), \
		        			descr='', mode='visible', ownerTag='', owner='infra')
			dhcpRsProv = cobra.model.dhcp.RsProv(dhcpRelayP, addr='{}'.format(dhcp_server), \
		        			tDn='uni/tn-{}-cp/out-{}/instP-{}'.format(site,dhcp_l3out,dhcp_l3out))		
		# Filter policy creation
		vzFilter = cobra.model.vz.Filter(fvTenant, ownerKey='', name='{}-allow-all'.format(site), descr='', ownerTag='')
		vzEntry = cobra.model.vz.Entry(vzFilter, tcpRules='', arpOpc='unspecified', applyToFrag='no', dToPort='unspecified', descr='', \
				prot='unspecified', sFromPort='unspecified', stateful='no', sToPort='unspecified', etherT='unspecified', \
				dFromPort='unspecified', name='allow-all')		

		for context_id in range (1, VRF_NO+1):
			vrf_name=config.get("{}-vrf{}".format(vpod_cp,context_id), "Name")
			bd_no=int(config.get("{}-vrf{}".format(vpod_cp,context_id), "BD_NO"))	
			l3_sub=config.get("{}-vrf{}".format(vpod_cp,context_id), "L3_SUB")
			if l3_sub=='NONE':
				continue
			l3_ip=int(config.get("{}-vrf{}".format(vpod_cp,context_id), "L3_IP"))
			l3_vlan=config.get("{}-vrf{}".format(vpod_cp,context_id), "vlan")				
			fvCtx = cobra.model.fv.Ctx(fvTenant, ownerKey='', name=vrf_name, descr='', knwMcastAct='permit', ownerTag='', pcEnfPref='enforced')
			fvAp = cobra.model.fv.Ap(fvTenant, name=vrf_name)

			if int(brownfield) == 0 or (int(brownfield) == 1 and int(mynode_id) == 301):
				# Contracts, Subjects and Filter associations
				vzBrCP = cobra.model.vz.BrCP(fvTenant, name='{}-epgs-to-fw-in-extEpg'.format(vrf_name))
				vzSubj = cobra.model.vz.Subj(vzBrCP, revFltPorts='yes', name='allow-all', consMatchT='AtleastOne', provMatchT='AtleastOne')
				vzRsSubjFiltAtt = cobra.model.vz.RsSubjFiltAtt(vzSubj, tnVzFilterName='{}-allow-all'.format(site))				
			
				# L3Out, NodeP, InterfaceP, l3extInstP policies creation	
				fvRsBgpCtxPol = cobra.model.fv.RsBgpCtxPol(fvCtx, tnBgpCtxPolName='')
				fvRsCtxToExtRouteTagPol = cobra.model.fv.RsCtxToExtRouteTagPol(fvCtx, tnL3extRouteTagPolName='')
				fvRsOspfCtxPol = cobra.model.fv.RsOspfCtxPol(fvCtx, tnOspfCtxPolName='')
				fvRsCtxToEpRet = cobra.model.fv.RsCtxToEpRet(fvCtx, tnFvEpRetPolName='')		
				l3_out_name="{}-fw-inside-l3out".format(vrf_name)
				l3extOut = cobra.model.l3ext.Out(fvTenant, ownerKey='', name=l3_out_name)
				l3extLNodeP = cobra.model.l3ext.LNodeP(l3extOut, ownerKey='', name='nodes-{}-{}'.format(L3_NODE_ID,int(L3_NODE_ID)+1), tag='yellow-green')
				l3extRsNodeL3OutAtt = cobra.model.l3ext.RsNodeL3OutAtt(l3extLNodeP, tDn='topology/pod-1/node-{}'.format(L3_NODE_ID),  \
							rtrId='1.{}.{}.{}'.format(L3_NODE_ID[:1],int(L3_NODE_ID[1:3]),l3_vlan))
				ipRouteP = cobra.model.ip.RouteP(l3extRsNodeL3OutAtt, name='', descr='', ip='0.0.0.0/0')
				ipNexthopP = cobra.model.ip.NexthopP(ipRouteP, name='', descr='', nhAddr='{}{}'.format(l3_sub, l3_ip+3))
				l3extRsNodeL3OutAtt2 = cobra.model.l3ext.RsNodeL3OutAtt(l3extLNodeP, tDn='topology/pod-1/node-{}'.format(int(L3_NODE_ID)+1),  \
							rtrId='1.{}.{}.{}'.format(L3_NODE_ID[:1],int(L3_NODE_ID[1:3])+1,l3_vlan))
				ipRouteP2 = cobra.model.ip.RouteP(l3extRsNodeL3OutAtt2, name='', descr='', ip='0.0.0.0/0')
				ipNexthopP2 = cobra.model.ip.NexthopP(ipRouteP2, name='', descr='', nhAddr='{}{}'.format(l3_sub, l3_ip+3))
				l3extLIfP = cobra.model.l3ext.LIfP(l3extLNodeP, ownerKey='', descr='', name='int-profile', tag='yellow-green')
	                	for intf_id in range (1, VPC_INT+1):
                			interface_id = config.get("L3_OUT", "VPC_INT_INTERFACE{}".format(intf_id))
                			L3_VPC_NAME=Create_PG_VPC_NAME(site,L3_NODE_ID,interface_id)
					l3extRsPathL3OutAtt = cobra.model.l3ext.RsPathL3OutAtt(l3extLIfP, addr='0.0.0.0', encap='vlan-{}'.format(l3_vlan), \
						ifInstT='ext-svi', tDn='topology/pod-1/protpaths-{}-{}/pathep-[{}]'.format(L3_NODE_ID,int(L3_NODE_ID)+1,L3_VPC_NAME))
				l3extMember = cobra.model.l3ext.Member(l3extRsPathL3OutAtt, addr='{}{}/29'.format(l3_sub, l3_ip+2), descr='', name='', side='B')
				l3extIp = cobra.model.l3ext.Ip(l3extMember, name='', descr='', addr='{}{}/29'.format(l3_sub, l3_ip))
				l3extMember2 = cobra.model.l3ext.Member(l3extRsPathL3OutAtt, addr='{}{}/29'.format(l3_sub, l3_ip+1), descr='', name='', side='A')
				l3extIp2 = cobra.model.l3ext.Ip(l3extMember2, name='', descr='', addr='{}{}/29'.format(l3_sub, l3_ip))
				l3extRsEctx = cobra.model.l3ext.RsEctx(l3extOut, tnFvCtxName=vrf_name)
				l3extRsL3DomAtt = cobra.model.l3ext.RsL3DomAtt(l3extOut, tDn='uni/l3dom-{}'.format(l3_dom))
				l3extInstP = cobra.model.l3ext.InstP(l3extOut, matchT='AtleastOne', name=l3_out_name, descr='')
				fvRsCustQosPol = cobra.model.fv.RsCustQosPol(l3extInstP, tnQosCustomPolName='')
				l3extSubnet = cobra.model.l3ext.Subnet(l3extInstP, name='', descr='', ip='0.0.0.0/0')	

			# Create BD, fvAEpg
			for bd_id in range (1, bd_no+1):
			    epg_no=config.get("{}-vrf{}".format(vpod_cp,context_id), "BD{}_EPG_NO".format(bd_id))
			    for epg_id in range(1, 1+int(epg_no)):
				bd_name=config.get("{}-vrf{}".format(vpod_cp,context_id), "BD{}_Name".format(bd_id))
				epg_name=config.get("{}-vrf{}".format(vpod_cp,context_id), "BD{}_EPG{}_Name".format(bd_id,epg_id))
				vlan_id=int(config.get("{}-vrf{}".format(vpod_cp,context_id), "BD{}_EPG{}_VLAN_NO".format(bd_id,epg_id)))
				subnet_no=config.get("{}-vrf{}".format(vpod_cp,context_id), "BD{}_SUBNET_NO".format(bd_id))
				
                                fvBD = cobra.model.fv.BD(fvTenant, unicastRoute='yes', unkMcastAct='flood', name=bd_name, unkMacUcastAct='proxy', 
								arpFlood='yes', limitIpLearnToSubnets='yes')
				fvRsCtx = cobra.model.fv.RsCtx(fvBD, tnFvCtxName=vrf_name)	


				fvAEPg = cobra.model.fv.AEPg(fvAp, name=epg_name)
				fvRsBd = cobra.model.fv.RsBd(fvAEPg, tnFvBDName=bd_name)
				fvRsDomAtt = cobra.model.fv.RsDomAtt(fvAEPg, tDn='uni/phys-{}-phys-dom'.format(site), instrImedcy='lazy', resImedcy='lazy')

				if int(subnet_no) != 0 and int(brownfield) != 1:
					for subnet_id in range (1,1+int(subnet_no)):
						subnet=config.get("{}-vrf{}".format(vpod_cp,context_id), "BD{}_GW_IP{}".format(bd_id,subnet_id))
						netmask=subnet.split('/')
						tmproute=netmask[0]
						myroute=tmproute.split('.')
						len=int(netmask[1])
						second='.'.join([str((0xffffffff << (32 - len) >> i) & 0xff) for i in [24, 16, 8, 0]])
						print 'route {}'.format(vrf_name),'{}.{}.{}.{} {}'.format(myroute[0],myroute[1],myroute[2],\
								int(myroute[3])-1,second),'{}{}'.format(l3_sub,int(l3_ip))
						fvSubnet = cobra.model.fv.Subnet(fvBD, scope='private', ip=subnet)

				# Define Provider/Consumer relationship between fvAEpg and l3extInstP
				fvRsCons = cobra.model.fv.RsCons(l3extInstP, tnVzBrCPName='{}-epgs-to-fw-in-extEpg'.format(vrf_name), prio='unspecified')
				for bd_id_1 in range (1, bd_no+1):
					fvRsProv = cobra.model.fv.RsProv(fvAEPg, tnVzBrCPName='{}-epgs-to-fw-in-extEpg'.format(vrf_name), matchT='AtleastOne')

				# EPG's static path binding										
				if (int(brownfield) != 2) and (int(brownfield) != 4) and int(mynode_id)< 900:
					sheet_id = int(mynode_id)
					sheet_ranges = wb['LEAF{}-{}'.format(sheet_id,sheet_id+1)]
					# fvTenant = cobra.model.fv.Tenant(topMo, name=tenant_name)	
					# fvAp = cobra.model.fv.Ap(fvTenant, name=vrf_name)	
					# fvAEPg = cobra.model.fv.AEPg(fvAp, name=epg_name)					
					for line in range (2, 100):
						if line==50 or line==51:
							continue								
						Node_ID=sheet_ranges['A{}'.format(line)].value
						Port=sheet_ranges['B{}'.format(line)].value
						Access=sheet_ranges['F{}'.format(line)].value
						Device=sheet_ranges['C{}'.format(line)].value
						Native=sheet_ranges['H{}'.format(line)].value
						VPC_PG=Create_PG_VPC_NAME(site,Node_ID,Port)
						vPOD=sheet_ranges['K{}'.format(line)].value
						if Access == 'vpcm':
							VPC_PG=sheet_ranges['D{}'.format(line)].value
						if Device !='SHUTDOWN' and  Native!= 'apic' and vPOD==site:
							if sheet_ranges['I{}'.format(line)].value != None:
								if isinrange(vlan_id,str(sheet_ranges['I{}'.format(line)].value)):
									if sheet_ranges['H{}'.format(line)].value != None:
										if isinrange(vlan_id,str(sheet_ranges['H{}'.format(line)].value)):
											if vlan_id==43 or vlan_id==51:
												if Access == 'Access':
													fvRsPathAtt = cobra.model.fv.RsPathAtt(fvAEPg, encap='vlan-{}'.format(vlan_id), \
															instrImedcy='lazy', mode='native', \
															tDn='topology/pod-1/paths-{}/pathep-[eth1/{}]'.format(Node_ID, Port[3:5]))
												elif (Access == 'vpc' or Access == 'vpcm' ) and Node_ID%2 != 0:
													fvRsPathAtt = cobra.model.fv.RsPathAtt(fvAEPg, encap='vlan-{}'.format(vlan_id), \
															instrImedcy='lazy', mode='native', \
															tDn='topology/pod-1/protpaths-{}-{}/pathep-[{}]'.format(sheet_id,sheet_id+1,VPC_PG))
											else:
                                                                                                dhcpLbl = cobra.model.dhcp.Lbl(fvBD, owner='tenant', name='{}-dhcp-relay'.format(site))
												if Access == 'Access':
													fvRsPathAtt = cobra.model.fv.RsPathAtt(fvAEPg, encap='vlan-{}'.format(vlan_id), \
															instrImedcy='lazy', mode='untagged', \
															tDn='topology/pod-1/paths-{}/pathep-[eth1/{}]'.format(Node_ID, Port[3:5]))
												elif (Access == 'vpc' or Access == 'vpcm' ) and Node_ID%2 != 0:
													fvRsPathAtt = cobra.model.fv.RsPathAtt(fvAEPg, encap='vlan-{}'.format(vlan_id), \
															instrImedcy='lazy', mode='untagged', \
															tDn='topology/pod-1/protpaths-{}-{}/pathep-[{}]'.format(sheet_id,sheet_id+1,VPC_PG))
										else:
											if Access == 'Access':									
												fvRsPathAtt = cobra.model.fv.RsPathAtt(fvAEPg, encap='vlan-{}'.format(vlan_id), \
														instrImedcy='lazy', mode='regular', \
														tDn='topology/pod-1/paths-{}/pathep-[eth1/{}]'.format(Node_ID, Port[3:5]))
											elif (Access == 'vpc' or Access == 'vpcm' ) and Node_ID%2 != 0:
												fvRsPathAtt = cobra.model.fv.RsPathAtt(fvAEPg, encap='vlan-{}'.format(vlan_id), \
														instrImedcy='lazy', mode='regular', \
														tDn='topology/pod-1/protpaths-{}-{}/pathep-[{}]'.format(sheet_id,sheet_id+1,VPC_PG))	
									else:
										if Access == 'Access':				
											fvRsPathAtt = cobra.model.fv.RsPathAtt(fvAEPg, encap='vlan-{}'.format(vlan_id), \
													instrImedcy='lazy', mode='regular', \
													tDn='topology/pod-1/paths-{}/pathep-[eth1/{}]'.format(Node_ID, Port[3:5]))
										elif (Access == 'vpc' or Access == 'vpcm' ) and Node_ID%2 != 0:
											fvRsPathAtt = cobra.model.fv.RsPathAtt(fvAEPg, encap='vlan-{}'.format(vlan_id), \
													instrImedcy='lazy', mode='regular', \
													tDn='topology/pod-1/protpaths-{}-{}/pathep-[{}]'.format(sheet_id,sheet_id+1,VPC_PG))												
							elif sheet_ranges['H{}'.format(line)].value != None and sheet_ranges['H{}'.format(line)].value !='apic' and \
												sheet_ranges['H{}'.format(line)].value !='span':
								if isinrange(vlan_id,str(sheet_ranges['H{}'.format(line)].value)):
									if vlan_id==43 or vlan_id==51:
										if Access == 'Access':
											fvRsPathAtt = cobra.model.fv.RsPathAtt(fvAEPg, encap='vlan-{}'.format(vlan_id), instrImedcy='lazy', \
													mode='native', tDn='topology/pod-1/paths-{}/pathep-[eth1/{}]'.format(Node_ID, Port[3:5]))
										elif (Access == 'vpc' or Access == 'vpcm' ) and Node_ID%2 != 0:
											fvRsPathAtt = cobra.model.fv.RsPathAtt(fvAEPg, encap='vlan-{}'.format(vlan_id), instrImedcy='lazy', \
													mode='native', tDn='topology/pod-1/protpaths-{}-{}/pathep-[{}]'.format(sheet_id,sheet_id+1,VPC_PG))
									else:
										if Access == 'Access':
											fvRsPathAtt = cobra.model.fv.RsPathAtt(fvAEPg, encap='vlan-{}'.format(vlan_id), instrImedcy='lazy', \
													mode='untagged', tDn='topology/pod-1/paths-{}/pathep-[eth1/{}]'.format(Node_ID, Port[3:5]))
										elif (Access == 'vpc' or Access == 'vpcm' ) and Node_ID%2 != 0:
											fvRsPathAtt = cobra.model.fv.RsPathAtt(fvAEPg, encap='vlan-{}'.format(vlan_id), instrImedcy='lazy', \
													mode='untagged', tDn='topology/pod-1/protpaths-{}-{}/pathep-[{}]'.format(sheet_id,sheet_id+1,VPC_PG))							
			md.reauth()
			commit_mo(md, fvTenant)
						
		print '\nCommiting Changes to the APIC MIT for tenants, APPs, EPGs and BDs'	
	t3 = time.time()
	diff=(datetime.datetime.fromtimestamp(t3) - datetime.datetime.fromtimestamp(t2))
	print ('difference is {0} seconds'.format(diff.total_seconds()))
	t4 = time.time()
	diff=(datetime.datetime.fromtimestamp(t4) - datetime.datetime.fromtimestamp(t1))
	print ('The Total Time for {} Tenants is {} seconds'.format(tenant_name,diff.total_seconds()))

def create_common_cp(md, site,brownfield, excel_file, config_file, mynode_id):
        
		# Will configure vpod specific subnets in FW L3Out and BB L3Out
		# in tenant common
        
		config = ConfigParser.ConfigParser()
                config.read(config_file)

                L3_NODE_ID= config.get("L3_OUT", "NODE_ID")
		BB_NODE_ID= int(config.get("BORDER_LEAF", "NODE_ID"))

		# rtr id for border leaves
                bb_router_id1=config.get("vrfcommon1", "router_id1")
                bb_router_id2=config.get("vrfcommon1", "router_id2")

		# rtr id for service nodes
		sn_router_id1=config.get("infra-sec-out-vrf1", "router_id1")
		sn_router_id2=config.get("infra-sec-out-vrf1", "router_id2")

                topMo = cobra.model.pol.Uni('')
                fvTenant = cobra.model.fv.Tenant(topMo, ownerKey='', name='common', descr='', ownerTag='')
		VRF_NO=int(config.get("myvars", "CP_VRF_NO"))
		vpod_cp=config.get("myvars", "VPOD_CP")
                
		for context_id in range (1, VRF_NO+1):
			# configure external EPG for BB L3Out

			l3_out_name=config.get("L3_OUT", "BB_L3OUT")
			for node_id in range (BB_NODE_ID,BB_NODE_ID+2, 2):
                            l3extOut = cobra.model.l3ext.Out(fvTenant, ownerKey='', name=l3_out_name, descr='', targetDscp='unspecified', enforceRtctrl='export', ownerTag='')
			    l3extInstP = cobra.model.l3ext.InstP(l3extOut, prio='unspecified', matchT='AtleastOne', name='vpods-bb-epg', descr='', targetDscp='unspecified')
			    l3extLNodeP = cobra.model.l3ext.LNodeP(l3extOut, ownerKey='', name='leaf-{}-{}'.format(node_id,node_id+1), descr='', \
						targetDscp='unspecified', tag='yellow-green', ownerTag='')
			    l3extRsNodeL3OutAtt = cobra.model.l3ext.RsNodeL3OutAtt(l3extLNodeP, rtrIdLoopBack='yes', rtrId='{}'.format(bb_router_id1), \
							tDn='topology/pod-1/node-{}'.format(node_id))
			    l3extRsNodeL3OutAtt2 = cobra.model.l3ext.RsNodeL3OutAtt(l3extLNodeP, rtrIdLoopBack='yes', rtrId='{}'.format(bb_router_id2), \
							tDn='topology/pod-1/node-{}'.format(node_id+1))

			    config_l3ext(config_file,l3extInstP,site,l3_out_name,context_id)

                        fvRsCons = cobra.model.fv.RsCons(l3extInstP, tnVzBrCPName='{}-fw-out'.format(site), prio='unspecified')

			# configure external EPG for FW L3Out
			l3_out_name="{}-fw-out".format(site)
                        l3extOut = cobra.model.l3ext.Out(fvTenant, ownerKey='', name=l3_out_name, descr='', targetDscp='unspecified', enforceRtctrl='export', ownerTag='')
			l3extInstP = cobra.model.l3ext.InstP(l3extOut, matchT='AtleastOne', name='{}-fw-out-extepg'.format(site), descr='')
                        l3extLNodeP = cobra.model.l3ext.LNodeP(l3extOut, ownerKey='', name='nodes-{}-{}'.format(L3_NODE_ID,int(L3_NODE_ID)+1), tag='yellow-green')
			l3extRsNodeL3OutAtt = cobra.model.l3ext.RsNodeL3OutAtt(l3extLNodeP, tDn='topology/pod-1/node-{}'.format(L3_NODE_ID), rtrId='{}'.format(sn_router_id1))
			l3extRsNodeL3OutAtt2 = cobra.model.l3ext.RsNodeL3OutAtt(l3extLNodeP, tDn='topology/pod-1/node-{}'.format(int(L3_NODE_ID)+1), rtrId='{}'.format(sn_router_id2))

			fvRsProv = cobra.model.fv.RsProv(l3extInstP, tnVzBrCPName='{}-fw-out'.format(site), matchT='AtleastOne')

			config_l3ext(config_file,l3extInstP,site,l3_out_name,context_id,l3extRsNodeL3OutAtt,l3extRsNodeL3OutAtt2)

		   	md.reauth()
                   	commit_mo(md, fvTenant)

def config_l3ext(config_file,l3extInstP,site,l3out_name,context_id,l3extRsNodeL3OutAtt=None,l3extRsNodeL3OutAtt2=None):

	# Will configure vpod specific subnet and static route in external EPG 
	# in tenant common

        config = ConfigParser.ConfigParser()
        config.read(config_file)

	l3_sub=config.get("infra-sec-out-vrf1", "L3_SUB_OUT")
	l3_ip=int(config.get("infra-sec-out-vrf1", "L3_IP_OUT"))

        vpod_cp=config.get("myvars", "VPOD_CP")
	bd_no=int(config.get("{}-vrf{}".format(vpod_cp,context_id), "BD_NO"))
        for bd_id in range (1, bd_no+1):
        	bd_name=config.get("{}-vrf{}".format(vpod_cp,context_id), "BD{}_Name".format(bd_id))
                subnet_no=config.get("{}-vrf{}".format(vpod_cp,context_id), "BD{}_SUBNET_NO".format(bd_id))

		bb_l3out_name=config.get("L3_OUT", "BB_L3OUT")
                for subnet_id in range (1,1+int(subnet_no)):
                    adv_check = int(config.get("{}-vrf{}".format(vpod_cp,context_id), "BD{}_ADV_CHK_SUBNET{}".format(bd_id,subnet_id)))
                    if adv_check==1:
                    	subnet=config.get("{}-vrf{}".format(vpod_cp,context_id), "BD{}_ADV_SUBNET{}".format(bd_id,subnet_id))
			if l3out_name!=bb_l3out_name:
                        	l3extSubnet = cobra.model.l3ext.Subnet(l3extInstP, aggregate='', ip='{}'.format(subnet), name='{}:{}'.format(site,bd_name), descr='')
                                ipRouteP = cobra.model.ip.RouteP(l3extRsNodeL3OutAtt, aggregate='no', ip='{}'.format(subnet), pref='1', name='{}:{}'.format(site,bd_name), descr='')
                                ipNexthopP = cobra.model.ip.NexthopP(ipRouteP, name='', descr='', nhAddr='{}{}'.format(l3_sub, l3_ip+3))
                                ipRouteP2 = cobra.model.ip.RouteP(l3extRsNodeL3OutAtt2, aggregate='no', ip='{}'.format(subnet), pref='1', name='{}:{}'.format(site,bd_name), descr='')
                                ipNexthopP2 = cobra.model.ip.NexthopP(ipRouteP2, name='', descr='', nhAddr='{}{}'.format(l3_sub, l3_ip+3))
			else:
				l3extSubnet = cobra.model.l3ext.Subnet(l3extInstP, scope='export-rtctrl', aggregate='', ip='{}'.format(subnet), name='{}:{}'.format(site,bd_name), descr='')

		# For adding NAT FW Subnet in FW-OUT
		if l3out_name!=bb_l3out_name:
			 subnet=config.get("myvars", "FW_NAT")
			 l3extSubnet = cobra.model.l3ext.Subnet(l3extInstP, aggregate='', ip='{}'.format(subnet), name='{}:{}'.format(site,bd_name), descr='')
			 ipRouteP = cobra.model.ip.RouteP(l3extRsNodeL3OutAtt, aggregate='no', ip='{}'.format(subnet), pref='1', name='{}:{}'.format(site,bd_name), descr='')
			 ipNexthopP = cobra.model.ip.NexthopP(ipRouteP, name='', descr='', nhAddr='{}{}'.format(l3_sub, l3_ip+3))
			 ipRouteP2 = cobra.model.ip.RouteP(l3extRsNodeL3OutAtt2, aggregate='no', ip='{}'.format(subnet), pref='1', name='{}:{}'.format(site,bd_name), descr='')
			 ipNexthopP2 = cobra.model.ip.NexthopP(ipRouteP2, name='', descr='', nhAddr='{}{}'.format(l3_sub, l3_ip+3))

def delete_common_cp(md, config_file):

	# Will delete the FW and BB L3Out in tenant common
        config = ConfigParser.ConfigParser()
        config.read(config_file)

	l3_out_namel= [config.get("L3_OUT", "FW_L3OUT")]
	l3_out_namel.append(config.get("L3_OUT", "BB_L3OUT"))

	topMo = cobra.model.pol.Uni('')
	fvTenant = cobra.model.fv.Tenant(topMo, ownerKey='', name='common', descr='', ownerTag='')
	for l3_out_name in l3_out_namel:
		l3extOut = cobra.model.l3ext.Out(fvTenant, ownerKey='', name=l3_out_name, descr='', targetDscp='unspecified', enforceRtctrl='export', ownerTag='')
		l3extOut.delete()

	md.reauth()
	commit_mo(md, fvTenant)
		

def delete_cp(md, site):
	"""
	Create tenant_count * bd_count BDs
	The tenant and application profile will be made if not present
	The naming scheme is always tenant-<unique_id>-<mo>-<count>
	"""
	# log into the APIC and create a directory object
	# Assuming every tenant will have a single app profile, 3x epgs app/web/db etc..
	# and single private network and 3 bds , one per each epg
	t1 = time.time()	
	tenant_name = '{}-cp'.format(site)
	topMo = cobra.model.pol.Uni('')
	fvTenant = cobra.model.fv.Tenant(topMo, name=tenant_name)
	fvTenant.delete()
	md.reauth()
	commit_mo(md, fvTenant)	

def main():
	# Main will capture all the parameters required to create tenants from the CLI
	# Change to True if you want to verify the server cert using TLS
	# Turning off by default
	# (True doesn't mandate HTTPS as it used to during the beta of the SDK)
	secure = False
	# Parse the command line for arguments
	parser = argparse.ArgumentParser(description='CLI arg parser')
	parser.add_argument('-a', '--apic', help='APIC IP Address or DNS name', required=True)
	parser.add_argument('-u', '--username', help='Username to log into the APIC.', required=True)
	parser.add_argument('-p', '--password', help='Password to log into the APIC.', required=True)
	parser.add_argument('-s', '--site', help='site to Create the APIC.', required=True)
	parser.add_argument('-c', '--create', help='Create Or Delete', required=True)
	parser.add_argument('-b', '--brownfield', help='Brownfield', required=True)
	parser.add_argument('-e', '--excel', help='excel file', required=True)	
	parser.add_argument('-i', '--ini', help='ini file', required=True)	
	parser.add_argument('-n', '--node', help='node id', required=True)		
	args = parser.parse_args()

	print "\n\nArguments received: %s, %s, %s, %s, %s %s %s %s %s\n" % (
		args.apic, args.username, args.password, args.site, args.create, args.brownfield, args.excel, args.ini, args.node)


	# Connect to the APIC and return the APIC MODirectory handle for further processing

	session_token = connect_to_apic(args.apic, args.username, args.password, secure)

	# call the main tenant creation procedure with session token and tenant creation parameters
	if (int(args.node))%2==1: 
		if int(args.create[:1])==1:
			create_tenants_main_ = create_cp(session_token,args.site,args.brownfield, args.excel, args.ini, args.node)
			# configure subnet and static route in common tenant L3Out
			create_common_cp(session_token,args.site,args.brownfield, args.excel, args.ini, args.node)
		elif int(args.create[:1])==0:
			create_tenants_main_ = delete_cp(session_token,args.site)
			#delete_common_cp(session_token,args.ini)


if __name__ == '__main__':
    main()


