import sys
sys.path.append('../')
from common import *
# import urllib3
# urllib3.disable_warnings()
# import requests
# requests.packages.urllib3.disable_warnings()

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
			time.sleep(30)
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
def create_common(md, site, brownfield, config_file):
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
		t2 = time.time()
		COMMON_VRF_NO=int(config.get("common", "VRF_NO"))
		L3_NODE_ID= config.get("L3_OUT", "NODE_ID")
        	VPC_EXT=int(config.get("L3_OUT", "VPC_EXT_NO"))
        	for context_id in range (1, COMMON_VRF_NO+1):
			vrf_name=config.get("vrfcommon{}".format(context_id), "Name")
			bb_l3_sub=config.get("vrfcommon{}".format(context_id), "BB_L3_SUB")	
			bb_l3_ip=int(config.get("vrfcommon{}".format(context_id), "BB_L3_IP"))		
			topMo = cobra.model.pol.Uni('')
			fvTenant = cobra.model.fv.Tenant(topMo, ownerKey='', name='common', descr='', ownerTag='', childAction='')
			ospfIfPol = cobra.model.ospf.IfPol(fvTenant, nwT='p2p', ownerKey='', name='OSPF-Interface-Policy', descr='', \
                                        ctrl='advert-subnet', helloIntvl='10', rexmitIntvl='5', xmitDelay='1', cost='unspecified', ownerTag='', prio='1', deadIntvl='40')
			aaaDomainRef = cobra.model.aaa.DomainRef(fvTenant, name='{}-sec-domain'.format(site))	
			aaaDomainRef.delete()
			fvCtx = cobra.model.fv.Ctx(fvTenant, name=vrf_name)
			fvAp = cobra.model.fv.Ap(fvTenant, name='{}-{}'.format(site,vrf_name))	
			ospfCtxPol = cobra.model.ospf.CtxPol(fvTenant, dist='110', maxEcmp='8', lsaArrivalIntvl='80', maxLsaSleepCnt='5', \
                                    grCtrl='helper', descr='', maxLsaThresh='75', maxLsaResetIntvl='10', lsaHoldIntvl='100', lsaStartIntvl='100', \
                                    lsaMaxIntvl='5000', maxLsaNum='20000', maxLsaAction='reject', spfMaxIntvl='5000', ownerTag='', spfHoldIntvl='100', \
                                    maxLsaSleepIntvl='5', ownerKey='', name='ospf-bb-gw-timers', lsaGpPacingIntvl='10', bwRef='40000', spfInitIntvl='100')
			fvRsOspfCtxPol = cobra.model.fv.RsOspfCtxPol(fvCtx, tnOspfCtxPolName='ospf-bb-gw-timers')
			l3_out_name="l3-out-{}".format(vrf_name)
			vzFilter = cobra.model.vz.Filter(fvTenant, ownerKey='', name='{}-allow-all'.format(site), descr='', ownerTag='')
			vzEntry = cobra.model.vz.Entry(vzFilter, tcpRules='', arpOpc='unspecified', applyToFrag='no', dToPort='unspecified', \
                                    descr='', prot='unspecified', icmpv4T='unspecified', sFromPort='unspecified', stateful='no', icmpv6T='unspecified', \
                                    sToPort='unspecified', etherT='unspecified', dFromPort='unspecified', name='allow-all')

			# Contract that will be exported for shared l3 out
			vzBrCP2 = cobra.model.vz.BrCP(fvTenant, ownerKey='', name='vpods-shd-bb-l3out'.format(site), scope='global', prio='unspecified', ownerTag='', descr='')
			vzSubj2 = cobra.model.vz.Subj(vzBrCP2, revFltPorts='yes', name='allow-all', prio='unspecified', descr='', consMatchT='AtleastOne', provMatchT='AtleastOne')
			vzRsSubjFiltAtt2 = cobra.model.vz.RsSubjFiltAtt(vzSubj2, tnVzFilterName='{}-allow-all'.format(site))

			BB_NODE_ID= int(config.get("BORDER_LEAF", "NODE_ID"))
			BB_PORT1=config.get("BORDER_LEAF", "Port1")
			BB_PORT2=config.get("BORDER_LEAF", "Port2")
			if int(brownfield) == 0:
			    for node_id in range (BB_NODE_ID,BB_NODE_ID+2, 2):
				l3extOut = cobra.model.l3ext.Out(fvTenant, ownerKey='', name=l3_out_name, descr='', targetDscp='unspecified', enforceRtctrl='export', ownerTag='')
				rtctrlProfile = cobra.model.rtctrl.Profile(l3extOut, ownerKey='', name='ospf-export', descr='', ownerTag='')
				rtctrlCtxP = cobra.model.rtctrl.CtxP(rtctrlProfile, name='ospf-export', descr='', order='0')
				rtctrlScope = cobra.model.rtctrl.Scope(rtctrlCtxP, name='', descr='')
				rtctrlRsScopeToAttrP = cobra.model.rtctrl.RsScopeToAttrP(rtctrlScope, tnRtctrlAttrPName='ospf-export')	
				rtctrlAttrP = cobra.model.rtctrl.AttrP(fvTenant, name='ospf-export', descr='')
				rtctrlSetRtMetric = cobra.model.rtctrl.SetRtMetric(rtctrlAttrP, metric='200', type='metric', name='', descr='')
				rtctrlSetRtMetricType = cobra.model.rtctrl.SetRtMetricType(rtctrlAttrP, type='metric-type', metricType='ospf-type2', descr='', name='')

				l3extLNodeP = cobra.model.l3ext.LNodeP(l3extOut, ownerKey='', name='leaf-{}-{}'.format(node_id,node_id+1), descr='', \
                                                targetDscp='unspecified', tag='yellow-green', ownerTag='')
				l3extRsL3DomAtt = cobra.model.l3ext.RsL3DomAtt(l3extOut, tDn='uni/l3dom-{}-l3-bb-dom'.format(site))
				router_id1=config.get("vrfcommon{}".format(context_id), "router_id1")
				router_id2=config.get("vrfcommon{}".format(context_id), "router_id2")
				l3extRsNodeL3OutAtt = cobra.model.l3ext.RsNodeL3OutAtt(l3extLNodeP, rtrIdLoopBack='yes', rtrId='{}'.format(router_id1), \
                                                        tDn='topology/pod-1/node-{}'.format(node_id))
				l3extRsNodeL3OutAtt2 = cobra.model.l3ext.RsNodeL3OutAtt(l3extLNodeP, rtrIdLoopBack='yes', rtrId='{}'.format(router_id2), \
                                                        tDn='topology/pod-1/node-{}'.format(node_id+1))
				l3extLIfP = cobra.model.l3ext.LIfP(l3extLNodeP, ownerKey='', tag='yellow-green', name='leaf{}-{}-int-profile'.format(node_id,node_id+1), \
                                                descr='', ownerTag='')
				ospfIfP = cobra.model.ospf.IfP(l3extLIfP, authKeyId='1', authType='md5', name='', descr='')
				ospfRsIfPol = cobra.model.ospf.RsIfPol(ospfIfP, tnOspfIfPolName='OSPF-Interface-Policy')
				l3extRsNdIfPol = cobra.model.l3ext.RsNdIfPol(l3extLIfP, tnNdIfPolName='')		
				l3extRsPathL3OutAtt = cobra.model.l3ext.RsPathL3OutAtt(l3extLIfP, addr='{}{}/31'.format(bb_l3_sub,bb_l3_ip+(node_id-BB_NODE_ID)*2), \
                                                        descr='', targetDscp='unspecified', mode='regular', encap='unknown', ifInstT='l3-port', mtu='inherit', \
                                                        tDn='topology/pod-1/paths-{}/pathep-[eth1/{}]'.format(node_id,BB_PORT1))
				l3extRsPathL3OutAtt2 = cobra.model.l3ext.RsPathL3OutAtt(l3extLIfP, addr='{}{}/31'.format(bb_l3_sub,bb_l3_ip+(node_id-BB_NODE_ID)*2+4), \
                                                        descr='', targetDscp='unspecified', mode='regular', encap='unknown', ifInstT='l3-port', mtu='inherit', \
                                                        tDn='topology/pod-1/paths-{}/pathep-[eth1/{}]'.format(node_id,BB_PORT2))
				l3extRsPathL3OutAtt3 = cobra.model.l3ext.RsPathL3OutAtt(l3extLIfP, addr='{}{}/31'.format(bb_l3_sub,bb_l3_ip+(node_id+1-BB_NODE_ID)*2), \
                                                        descr='', targetDscp='unspecified', mode='regular', encap='unknown', ifInstT='l3-port', mtu='inherit', \
                                                        tDn='topology/pod-1/paths-{}/pathep-[eth1/{}]'.format(node_id+1,BB_PORT1))
				l3extRsPathL3OutAtt4 = cobra.model.l3ext.RsPathL3OutAtt(l3extLIfP, addr='{}{}/31'.format(bb_l3_sub,bb_l3_ip+(node_id+1-BB_NODE_ID)*2+4), \
                                                        descr='', targetDscp='unspecified', mode='regular', encap='unknown', ifInstT='l3-port', mtu='inherit', \
                                                        tDn='topology/pod-1/paths-{}/pathep-[eth1/{}]'.format(node_id+1,BB_PORT2))				
				l3extRsEctx = cobra.model.l3ext.RsEctx(l3extOut, tnFvCtxName=vrf_name)
				l3extInstP = cobra.model.l3ext.InstP(l3extOut, prio='unspecified', matchT='AtleastOne', name=l3_out_name, descr='', targetDscp='unspecified')
				fvRsCons = cobra.model.fv.RsCons(l3extInstP, tnVzBrCPName='{}-fw-to-bb'.format(site), prio='unspecified')
				fvRsCustQosPol = cobra.model.fv.RsCustQosPol(l3extInstP, tnQosCustomPolName='')

				l3extSubnet = cobra.model.l3ext.Subnet(l3extInstP, scope='export-rtctrl,import-security,shared-rtctrl', aggregate='', ip='0.0.0.0/0', name='', descr='')	
				fvRsProv = cobra.model.fv.RsProv(l3extInstP, tnVzBrCPName='{}-fw-to-bb'.format(site), matchT='AtleastOne', prio='unspecified')
                                fvRsProv2 = cobra.model.fv.RsProv(l3extInstP, tnVzBrCPName='vpods-shd-bb-l3out', matchT='AtleastOne', prio='unspecified')
				ospfExtP = cobra.model.ospf.ExtP(l3extOut, areaCtrl='redistribute,summary', areaId='0.0.0.100', areaType='regular', areaCost='1', descr='')					
			md.reauth()
			commit_mo(md, fvTenant)
			topMo = cobra.model.pol.Uni('')
			fvTenant = cobra.model.fv.Tenant(topMo, ownerKey='', name='common', descr='', ownerTag='')		
			if int(brownfield) == 0:
			    FW_L3OUT_NO=int(config.get("myvars", "FW_L3OUT_NO"))
		            routerid1=config.get("L3_OUT", "router_id1")
			    routerid2=config.get("L3_OUT", "router_id2")

			    for l3_out in range (1, FW_L3OUT_NO+1):
			        vpod=config.get("vpod-fw-l3out{}".format(l3_out), "vpod")	
				l3_out_name="{}-fw-out".format(vpod)
				l3_sub=config.get("vpod-fw-l3out{}".format(l3_out), "L3_SUB_OUT")
				l3_ip=int(config.get("vpod-fw-l3out{}".format(l3_out), "L3_IP_OUT"))
				l3_vlan=config.get("vpod-fw-l3out{}".format(l3_out), "vlan_out")

				vzBrCP = cobra.model.vz.BrCP(fvTenant, ownerKey='', name='{}-fw-out'.format(vpod), prio='unspecified', ownerTag='', descr='')
				vzSubj = cobra.model.vz.Subj(vzBrCP, revFltPorts='yes', name='allow-all', prio='unspecified', descr='', consMatchT='AtleastOne', provMatchT='AtleastOne')
				vzRsSubjFiltAtt = cobra.model.vz.RsSubjFiltAtt(vzSubj, tnVzFilterName='vpods-allow-all')

				l3extOut = cobra.model.l3ext.Out(fvTenant, ownerKey='', name=l3_out_name, descr='', targetDscp='unspecified', enforceRtctrl='export', ownerTag='')
				l3extLNodeP = cobra.model.l3ext.LNodeP(l3extOut, ownerKey='', name='nodes-{}-{}'.format(L3_NODE_ID,int(L3_NODE_ID)+1), tag='yellow-green')
				l3extRsNodeL3OutAtt = cobra.model.l3ext.RsNodeL3OutAtt(l3extLNodeP, tDn='topology/pod-1/node-{}'.format(L3_NODE_ID), rtrId='{}'.format(routerid1))  
				l3extRsNodeL3OutAtt2 = cobra.model.l3ext.RsNodeL3OutAtt(l3extLNodeP, tDn='topology/pod-1/node-{}'.format(int(L3_NODE_ID)+1), rtrId='{}'.format(routerid2)) 
                		l3extLIfP = cobra.model.l3ext.LIfP(l3extLNodeP, ownerKey='', descr='', name='int-profile', tag='yellow-green')
                		for intf_id in range (1, VPC_EXT+1):
                        		interface_id = config.get("L3_OUT", "VPC_EXT_INTERFACE{}".format(intf_id))
                        		L3_VPC_NAME=Create_PG_VPC_NAME(site,L3_NODE_ID,interface_id)
                        		l3extRsPathL3OutAtt = cobra.model.l3ext.RsPathL3OutAtt(l3extLIfP, addr='0.0.0.0', encap='vlan-{}'.format(l3_vlan), \
                                               ifInstT='ext-svi', tDn='topology/pod-1/protpaths-{}-{}/pathep-[{}]'.format(L3_NODE_ID,int(L3_NODE_ID)+1,L3_VPC_NAME))
					l3extMember = cobra.model.l3ext.Member(l3extRsPathL3OutAtt, addr='{}{}/29'.format(l3_sub, l3_ip+2), descr='', name='', side='B')
					l3extIp = cobra.model.l3ext.Ip(l3extMember, name='', descr='', addr='{}{}/29'.format(l3_sub, l3_ip))
					l3extMember = cobra.model.l3ext.Member(l3extRsPathL3OutAtt, addr='{}{}/29'.format(l3_sub, l3_ip+1), descr='', name='', side='A')
					l3extIp = cobra.model.l3ext.Ip(l3extMember, name='', descr='', addr='{}{}/29'.format(l3_sub, l3_ip))
				l3extRsEctx = cobra.model.l3ext.RsEctx(l3extOut, tnFvCtxName=vrf_name)
				#l3extRsL3DomAtt = cobra.model.l3ext.RsL3DomAtt(l3extOut, tDn='uni/l3dom-{}-l3-fw-dom'.format(site))
				l3extRsL3DomAtt = cobra.model.l3ext.RsL3DomAtt(l3extOut, tDn='uni/l3dom-vpod99-l3-fw-dom')
			
		        md.reauth()
		        commit_mo(md, fvTenant)
		print '\nCommiting Changes to the APIC MIT for tenants, APPs, EPGs and BDs'	
	t3 = time.time()
	diff=(datetime.datetime.fromtimestamp(t3) - datetime.datetime.fromtimestamp(t2))
	print ('difference is {0} seconds'.format(diff.total_seconds()))
	t4 = time.time()
	diff=(datetime.datetime.fromtimestamp(t4) - datetime.datetime.fromtimestamp(t1))
	print ('The Total Time for {} Tenants is {} seconds'.format('common',diff.total_seconds()))

def delete_common(md, site, config_file):
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
		t2 = time.time()
		# the top level object on which operations will be made
		# Create the tenant, private network/vrf/context, and security domain
		# topMo = cobra.model.pol.Uni('')
		# fvTenant = cobra.model.fv.Tenant(topMo, ownerKey='', name='common', descr='', ownerTag='')
		# spanVSrcGrp = cobra.model.span.VSrcGrp(fvTenant, ownerKey='', ownerTag='', name='default', descr='', adminSt='start')
		# spanVDestGrp = cobra.model.span.VDestGrp(fvTenant, ownerKey='', name='default', descr='', ownerTag='')
		# # build the request using cobra syntax			
		# md.reauth()
		# commit_mo(md, topMo)
		COMMON_VRF_NO=int(config.get("common", "VRF_NO"))
		for context_id in range (1, COMMON_VRF_NO+1):
			vrf_name=config.get("vrfcommon{}".format(context_id), "Name")
			bb_l3_sub=config.get("vrfcommon{}".format(context_id), "BB_L3_SUB")	
			bb_l3_ip=int(config.get("vrfcommon{}".format(context_id), "BB_L3_IP"))	
			topMo = cobra.model.pol.Uni('')
			fvTenant = cobra.model.fv.Tenant(topMo, ownerKey='', name='common', descr='', ownerTag='')			
			ospfIfPol = cobra.model.ospf.IfPol(fvTenant, nwT='p2p', ownerKey='', name='OSPF-Interface-Policy', descr='', ctrl='advert-subnet', \
					helloIntvl='10', rexmitIntvl='5', xmitDelay='1', cost='unspecified', ownerTag='', prio='1', deadIntvl='40')
			ospfIfPol.delete()
			aaaDomainRef = cobra.model.aaa.DomainRef(fvTenant, name='{}-sec-domain'.format(site))
			# dhcpRelayP = cobra.model.dhcp.RelayP(fvTenant, ownerKey='', name='epg82-dhcp-relay-profile', descr='', mode='visible', ownerTag='', owner='infra')
			# dhcpRsProv = cobra.model.dhcp.RsProv(dhcpRelayP, addr='10.23.199.202', tDn='uni/tn-vpod1-inside/out-L3-out-cloudmgmt/instP-ext-epg-cloudmgmt')
			fvCtx = cobra.model.fv.Ctx(fvTenant, name=vrf_name)
			fvCtx.delete()
			fvAp = cobra.model.fv.Ap(fvTenant, name='{}-{}'.format(site,vrf_name))	
			fvAp.delete()
			l3_out_name="l3-out-{}".format(vrf_name)
			vzFilter = cobra.model.vz.Filter(fvTenant, ownerKey='', name='{}-allow-all'.format(site), descr='', ownerTag='')
			vzFilter.delete()
			vzBrCP = cobra.model.vz.BrCP(fvTenant, ownerKey='', name='{}-fw-to-bb'.format(site), prio='unspecified', ownerTag='', descr='')
			vzBrCP.delete()	
			l3extOut = cobra.model.l3ext.Out(fvTenant, ownerKey='', name=l3_out_name, descr='', targetDscp='unspecified', enforceRtctrl='export', ownerTag='')
			l3extOut.delete()				
			md.reauth()
			commit_mo(md, topMo)	
			l3_out_name="{}-l3-fw-out".format(site,vrf_name)
			topMo = cobra.model.pol.Uni('')
			fvTenant = cobra.model.fv.Tenant(topMo, ownerKey='', name='common', descr='', ownerTag='')			
			l3_sub=config.get("vrfcommon{}".format(context_id), "L3_SUB")
			l3_ip=int(config.get("vrfcommon{}".format(context_id), "L3_IP"))
			l3_vlan=config.get("vrfcommon{}".format(context_id), "vlan")	
			l3extOut = cobra.model.l3ext.Out(fvTenant, ownerKey='', name=l3_out_name, descr='', targetDscp='unspecified', enforceRtctrl='export', ownerTag='')
			l3extOut.delete()

			md.reauth()
			commit_mo(md, topMo)
		print '\nCommiting Changes to the APIC MIT for tenants, APPs, EPGs and BDs'	
	t3 = time.time()
	diff=(datetime.datetime.fromtimestamp(t3) - datetime.datetime.fromtimestamp(t2))
	print ('difference is {0} seconds'.format(diff.total_seconds()))
	t4 = time.time()
	diff=(datetime.datetime.fromtimestamp(t4) - datetime.datetime.fromtimestamp(t1))
	print ('The Total Time for {} Tenants is {} seconds'.format('common',diff.total_seconds()))

def create_ospf_key(site,host,username, password, secure, config_file):
	name_pwd = {'aaaUser': {'attributes': {'name': '{}'.format(username), 'pwd': '{}'.format(password)}}}
	json_credentials = json.dumps(name_pwd)
	# log in to API
	base_url = 'https://{}/api/'.format(host)
	login_url = base_url + 'aaaLogin.json'
	post_response = requests.post(login_url, data=json_credentials, verify=secure)
	# get token from login response structure
	auth = json.loads(post_response.text)
	login_attributes = auth['imdata'][0]['aaaLogin']['attributes']
	auth_token = login_attributes['token']
	# create cookie array from token
	cookies = {}
	cookies['APIC-Cookie'] = auth_token	
	config = ConfigParser.ConfigParser()
	config.read(config_file)
	OSPFKEY=config.get("vrfcommon1", "OSPFKEY")
	NODE_ID=int(config.get("BORDER_LEAF", "NODE_ID"))
	URL=base_url+'node/mo/uni/tn-common/out-l3-out-backbone/lnodep-leaf-{}-{}/lifp-leaf{}-{}-int-profile/ospfIfP.json'.format(NODE_ID,NODE_ID+1,NODE_ID,NODE_ID+1)
	nodes={"ospfIfP":{"attributes":{"dn":'uni/tn-common/out-l3-out-backbone/lnodep-leaf-{}-{}/lifp-leaf{}-{}-int-profile/ospfIfP'.format(NODE_ID,NODE_ID+1,NODE_ID,NODE_ID+1),\
				"authKey":'{}'.format(OSPFKEY)},"children":[]}}
	data=json.dumps(nodes)	
	post_response = requests.post(URL, cookies=cookies, data=data, verify=secure)

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
	parser.add_argument('-i', '--ini', help='ini file', required=True)	
	args = parser.parse_args()

	print "\n\nArguments received: %s, %s, %s, %s, %s %s %s \n" % (
		args.apic, args.username, args.password, args.site, args.create, args.brownfield, args.ini)

	# Connect to the APIC and return the APIC MODirectory handle for further processing
	session_token = connect_to_apic(args.apic, args.username, args.password, secure)
	
	# call the main tenant creation procedure with session token and tenant creation parameters
	tenantMo = session_token.lookupByClass('fvTenant', propFilter='eq(fvTenant.name, "common")')
	if tenantMo:
		if int(args.create[:1])==1:
			create_tenants_main_ = create_common(session_token,args.site, args.brownfield, args.ini)
			create_ospf_key(args.site, args.apic ,args.username, args.password, secure, args.ini)
		elif int(args.create[:1])==0:
			create_tenants_main_ = delete_common(session_token,args.site, args.ini)
	

if __name__ == '__main__':
    main()


