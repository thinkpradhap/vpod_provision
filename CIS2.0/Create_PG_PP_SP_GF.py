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
def add_dom_aep_leaf8xx(md, site):
	polUni = cobra.model.pol.Uni('')
	infraInfra = cobra.model.infra.Infra(polUni)
	# build the request using cobra syntax
	infraAttEntityP = cobra.model.infra.AttEntityP(infraInfra, ownerKey='', name='{}-leaf8xx-aep'.format(site), descr='', ownerTag='')
	infraRsDomP = cobra.model.infra.RsDomP(infraAttEntityP, tDn='uni/phys-{}-phys-dom'.format(site))
	md.reauth()
	commit_mo(md, infraInfra)	
def del_dom_aep_leaf8xx(md, site):
	polUni = cobra.model.pol.Uni('')
	infraInfra = cobra.model.infra.Infra(polUni)
	# build the request using cobra syntax
	infraAttEntityP = cobra.model.infra.AttEntityP(infraInfra, ownerKey='', name='{}-leaf8xx-aep'.format(site), descr='', ownerTag='')
	infraRsDomP = cobra.model.infra.RsDomP(infraAttEntityP, tDn='uni/phys-{}-phys-dom'.format(site))
	infraRsDomP.delete()
	md.reauth()
	commit_mo(md, infraInfra)		
def Create_span_dst(md,Node_ID,port):
	polUni = cobra.model.pol.Uni('')
	infraInfra = cobra.model.infra.Infra(polUni)
	# build the request using cobra syntax
	spanDestGrp = cobra.model.span.DestGrp(infraInfra, ownerKey='', name='DST', descr='', ownerTag='')
	spanDest = cobra.model.span.Dest(spanDestGrp, ownerKey='', name='Leaf{}-Eth{}'.format(Node_ID,str(port).zfill(2)),descr='', ownerTag='')
	spanRsDestPathEp = cobra.model.span.RsDestPathEp(spanDest, tDn='topology/pod-1/paths-{}/pathep-[eth1/{}]'.format(Node_ID,int(port)))
	md.reauth()
	commit_mo(md, infraInfra)	
def Delete_span_dst(md):
	polUni = cobra.model.pol.Uni('')
	infraInfra = cobra.model.infra.Infra(polUni)
	# build the request using cobra syntax
	spanDestGrp = cobra.model.span.DestGrp(infraInfra, ownerKey='', name='DST', descr='', ownerTag='')
	spanDestGrp.delete()
	md.reauth()
	commit_mo(md, infraInfra)		
def Create_vpc_pair(md,Node_ID):
	polUni = cobra.model.pol.Uni('')
	fabricInst = cobra.model.fabric.Inst(polUni)
	fabricProtPol = cobra.model.fabric.ProtPol(fabricInst)
	# build the request using cobra syntax
	fabricExplicitGEp = cobra.model.fabric.ExplicitGEp(fabricProtPol, id='{}'.format(Node_ID), name='leaf{}-{}-vpc'.format(Node_ID,int(Node_ID)+1))
	fabricRsVpcInstPol = cobra.model.fabric.RsVpcInstPol(fabricExplicitGEp, tnVpcInstPolName='vpc-policy')
	fabricNodePEp = cobra.model.fabric.NodePEp(fabricExplicitGEp, id='{}'.format(Node_ID), descr='', name='')
	fabricNodePEp2 = cobra.model.fabric.NodePEp(fabricExplicitGEp, id='{}'.format(int(Node_ID)+1), descr='', name='')
	md.reauth()
	commit_mo(md, fabricInst)		
def Delete_vpc_pair(md,Node_ID):
	polUni = cobra.model.pol.Uni('')
	fabricInst = cobra.model.fabric.Inst(polUni)
	fabricProtPol = cobra.model.fabric.ProtPol(fabricInst)
	# build the request using cobra syntax
	fabricExplicitGEp = cobra.model.fabric.ExplicitGEp(fabricProtPol, id='{}'.format(Node_ID), name='leaf{}-{}-vpc'.format(Node_ID,int(Node_ID)+1))
	fabricExplicitGEp.delete()
	md.reauth()
	commit_mo(md, fabricInst)		
def Create_PG_Access_NAME(site,Node_ID,Port):
	return 'leaf{}-{}-pg'.format(Node_ID,Port)
def Create_PG_VPC_NAME(site,Node_ID,Port):
	return 'leaf{}-{}-{}-pg'.format(Node_ID,int(Node_ID)+1,Port)
def Create_PP_Access_NAME(site,Node_ID):
	return 'leaf{}-access-profile'.format(Node_ID)
def Create_PP_VPC_NAME(site,Node_ID):
	return 'leaf{}-{}-vpc-profile'.format(Node_ID,int(Node_ID)+1)	
def Create_PG_Access(md,name,desc,aep, speed):	
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/funcprof/accportgrp-{}'.format(name))
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	# build the request using cobra syntax
	infraAccPortGrp = cobra.model.infra.AccPortGrp(topMo, ownerKey='', name='{}'.format(name), descr='{}'.format(desc), ownerTag='')
	infraRsMonIfInfraPol = cobra.model.infra.RsMonIfInfraPol(infraAccPortGrp, tnMonInfraPolName='')
	infraRsLldpIfPol = cobra.model.infra.RsLldpIfPol(infraAccPortGrp, tnLldpIfPolName='lldp-on')
	infraRsStpIfPol = cobra.model.infra.RsStpIfPol(infraAccPortGrp, tnStpIfPolName='bpdu-guard-on')
	infraRsCdpIfPol = cobra.model.infra.RsCdpIfPol(infraAccPortGrp, tnCdpIfPolName='cdp-on')
	infraRsL2IfPol = cobra.model.infra.RsL2IfPol(infraAccPortGrp, tnL2IfPolName='l2-int-policy-global')
	infraRsAttEntP = cobra.model.infra.RsAttEntP(infraAccPortGrp, tDn='uni/infra/attentp-{}'.format(aep))
	infraRsMcpIfPol = cobra.model.infra.RsMcpIfPol(infraAccPortGrp, tnMcpIfPolName='')
	infraRsStormctrlIfPol = cobra.model.infra.RsStormctrlIfPol(infraAccPortGrp, tnStormctrlIfPolName='')
	if speed==1000:
		infraRsHIfPol = cobra.model.infra.RsHIfPol(infraAccPortGrp, tnFabricHIfPolName='1g-port')
	elif speed==10000:
		infraRsHIfPol = cobra.model.infra.RsHIfPol(infraAccPortGrp, tnFabricHIfPolName='10g-port')
	elif speed==40000:
		infraRsHIfPol = cobra.model.infra.RsHIfPol(infraAccPortGrp, tnFabricHIfPolName='40g-port')
	md.reauth()
	commit_mo(md, topMo)	
def Delete_PG_Access(md,name,desc,aep):	
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/funcprof/accportgrp-{}'.format(name))
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	# build the request using cobra syntax
	infraAccPortGrp = cobra.model.infra.AccPortGrp(topMo, ownerKey='', name='{}'.format(name), descr='{}'.format(desc), ownerTag='')
	infraAccPortGrp.delete()
	md.reauth()
	commit_mo(md, topMo)	
def Create_PG_VPC(md,name,desc,aep, speed):	
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/funcprof/accbundle-{}'.format(name))
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	# build the request using cobra syntax
	infraAccBndlGrp = cobra.model.infra.AccBndlGrp(topMo, ownerKey='', name='{}'.format(name), descr='{}'.format(desc), lagT='node', ownerTag='')
	infraRsMonIfInfraPol = cobra.model.infra.RsMonIfInfraPol(infraAccBndlGrp, tnMonInfraPolName='')
	infraRsLldpIfPol = cobra.model.infra.RsLldpIfPol(infraAccBndlGrp, tnLldpIfPolName='lldp-on')
	infraRsStpIfPol = cobra.model.infra.RsStpIfPol(infraAccBndlGrp, tnStpIfPolName='bpdu-guard-on')
	infraRsCdpIfPol = cobra.model.infra.RsCdpIfPol(infraAccBndlGrp, tnCdpIfPolName='cdp-on')
	infraRsL2IfPol = cobra.model.infra.RsL2IfPol(infraAccBndlGrp, tnL2IfPolName='l2-int-policy-global')
	infraRsAttEntP = cobra.model.infra.RsAttEntP(infraAccBndlGrp, tDn='uni/infra/attentp-{}'.format(aep))
	infraRsMcpIfPol = cobra.model.infra.RsMcpIfPol(infraAccBndlGrp, tnMcpIfPolName='')
	infraRsLacpPol = cobra.model.infra.RsLacpPol(infraAccBndlGrp, tnLacpLagPolName='lacp-active')
	infraRsStormctrlIfPol = cobra.model.infra.RsStormctrlIfPol(infraAccBndlGrp, tnStormctrlIfPolName='')
	if speed==1000:
		infraRsHIfPol = cobra.model.infra.RsHIfPol(infraAccBndlGrp, tnFabricHIfPolName='1g-port')
	elif speed==10000:
		infraRsHIfPol = cobra.model.infra.RsHIfPol(infraAccBndlGrp, tnFabricHIfPolName='10g-port')
	elif speed==40000:
		infraRsHIfPol = cobra.model.infra.RsHIfPol(infraAccBndlGrp, tnFabricHIfPolName='40g-port')
	md.reauth()
	commit_mo(md, topMo)
def Create_PG_VPC_no_suspend(md,name,desc,aep, speed):	
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/funcprof/accbundle-{}'.format(name))
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	# build the request using cobra syntax
	infraAccBndlGrp = cobra.model.infra.AccBndlGrp(topMo, ownerKey='', name='{}'.format(name), descr='{}'.format(desc), lagT='node', ownerTag='')
	infraRsMonIfInfraPol = cobra.model.infra.RsMonIfInfraPol(infraAccBndlGrp, tnMonInfraPolName='')
	infraRsLldpIfPol = cobra.model.infra.RsLldpIfPol(infraAccBndlGrp, tnLldpIfPolName='lldp-on')
	infraRsStpIfPol = cobra.model.infra.RsStpIfPol(infraAccBndlGrp, tnStpIfPolName='bpdu-guard-on')
	infraRsCdpIfPol = cobra.model.infra.RsCdpIfPol(infraAccBndlGrp, tnCdpIfPolName='cdp-on')
	infraRsL2IfPol = cobra.model.infra.RsL2IfPol(infraAccBndlGrp, tnL2IfPolName='l2-int-policy-global')
	infraRsAttEntP = cobra.model.infra.RsAttEntP(infraAccBndlGrp, tDn='uni/infra/attentp-{}'.format(aep))
	infraRsMcpIfPol = cobra.model.infra.RsMcpIfPol(infraAccBndlGrp, tnMcpIfPolName='')
	infraRsLacpPol = cobra.model.infra.RsLacpPol(infraAccBndlGrp, tnLacpLagPolName='lacp-active-no-suspend')
	infraRsStormctrlIfPol = cobra.model.infra.RsStormctrlIfPol(infraAccBndlGrp, tnStormctrlIfPolName='')
	if speed==1000:
		infraRsHIfPol = cobra.model.infra.RsHIfPol(infraAccBndlGrp, tnFabricHIfPolName='1g-port')
	elif speed==10000:
		infraRsHIfPol = cobra.model.infra.RsHIfPol(infraAccBndlGrp, tnFabricHIfPolName='10g-port')
	elif speed==40000:
		infraRsHIfPol = cobra.model.infra.RsHIfPol(infraAccBndlGrp, tnFabricHIfPolName='40g-port')
	md.reauth()
	commit_mo(md, topMo)	
def Create_PG_VPC_no_BPDU(md,name,desc,aep, speed):	
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/funcprof/accbundle-{}'.format(name))
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	# build the request using cobra syntax
	infraAccBndlGrp = cobra.model.infra.AccBndlGrp(topMo, ownerKey='', name='{}'.format(name), descr='{}'.format(desc), lagT='node', ownerTag='')
	infraRsMonIfInfraPol = cobra.model.infra.RsMonIfInfraPol(infraAccBndlGrp, tnMonInfraPolName='')
	infraRsLldpIfPol = cobra.model.infra.RsLldpIfPol(infraAccBndlGrp, tnLldpIfPolName='lldp-on')
	infraRsStpIfPol = cobra.model.infra.RsStpIfPol(infraAccBndlGrp, tnStpIfPolName='default')
	infraRsCdpIfPol = cobra.model.infra.RsCdpIfPol(infraAccBndlGrp, tnCdpIfPolName='cdp-on')
	infraRsL2IfPol = cobra.model.infra.RsL2IfPol(infraAccBndlGrp, tnL2IfPolName='l2-int-policy-global')
	infraRsAttEntP = cobra.model.infra.RsAttEntP(infraAccBndlGrp, tDn='uni/infra/attentp-{}'.format(aep))
	infraRsMcpIfPol = cobra.model.infra.RsMcpIfPol(infraAccBndlGrp, tnMcpIfPolName='')
	infraRsLacpPol = cobra.model.infra.RsLacpPol(infraAccBndlGrp, tnLacpLagPolName='lacp-active')
	infraRsStormctrlIfPol = cobra.model.infra.RsStormctrlIfPol(infraAccBndlGrp, tnStormctrlIfPolName='')
	if speed==1000:
		infraRsHIfPol = cobra.model.infra.RsHIfPol(infraAccBndlGrp, tnFabricHIfPolName='1g-port')
	elif speed==10000:
		infraRsHIfPol = cobra.model.infra.RsHIfPol(infraAccBndlGrp, tnFabricHIfPolName='10g-port')
	elif speed==40000:
		infraRsHIfPol = cobra.model.infra.RsHIfPol(infraAccBndlGrp, tnFabricHIfPolName='40g-port')
	md.reauth()
	commit_mo(md, topMo)	
def Delete_PG_VPC(md,name,desc,aep):	
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/funcprof/accbundle-{}'.format(name))
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	# build the request using cobra syntax
	infraAccBndlGrp = cobra.model.infra.AccBndlGrp(topMo, ownerKey='', name='{}'.format(name), descr='{}'.format(desc), lagT='node', ownerTag='')
	infraAccBndlGrp.delete()
	md.reauth()
	commit_mo(md, topMo)	
def Create_access_policy_profile(md,pp_name,pg_name,port,description):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/accportprof-{}'.format(pp_name))
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	# build the request using cobra syntax
	infraAccPortP = cobra.model.infra.AccPortP(topMo, ownerKey='', name='{}'.format(pp_name), descr='', ownerTag='')
	infraHPortS = cobra.model.infra.HPortS(infraAccPortP, ownerKey='', type='range', name='{}'.format(pg_name), descr='{}'.format(description), ownerTag='')
	infraRsAccBaseGrp = cobra.model.infra.RsAccBaseGrp(infraHPortS, fexId='101', tDn='uni/infra/funcprof/accportgrp-{}'.format(pg_name))
	infraPortBlk = cobra.model.infra.PortBlk(infraHPortS, name='block{}'.format(port), descr='', fromPort='{}'.format(port), fromCard='1', toPort='{}'.format(port), toCard='1')
	md.reauth()
	commit_mo(md, topMo)
def Create_vpc_policy_profile(md,pp_name,pg_name,port,description):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/accportprof-{}'.format(pp_name))
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	# build the request using cobra syntax
	infraAccPortP = cobra.model.infra.AccPortP(topMo, ownerKey='', name='{}'.format(pp_name), descr='', ownerTag='')
	infraHPortS = cobra.model.infra.HPortS(infraAccPortP, ownerKey='', type='range', name='{}'.format(pg_name), descr='{}'.format(description), ownerTag='')
	infraRsAccBaseGrp = cobra.model.infra.RsAccBaseGrp(infraHPortS, fexId='101', tDn='uni/infra/funcprof/accbundle-{}'.format(pg_name))
	infraPortBlk = cobra.model.infra.PortBlk(infraHPortS, name='block{}'.format(port), descr='', fromPort='{}'.format(port), fromCard='1', toPort='{}'.format(port), toCard='1')
	md.reauth()
	commit_mo(md, topMo)	
def Delete_access_policy_profile(md,pp_name,pg_name,port,description):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/accportprof-{}'.format(pp_name))
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	# build the request using cobra syntax
	infraAccPortP = cobra.model.infra.AccPortP(topMo, ownerKey='', name='{}'.format(pp_name), descr='', ownerTag='')
	infraAccPortP.delete()
	md.reauth()
	commit_mo(md, topMo)	
def Delete_vpc_policy_profile(md,pp_name,pg_name,port,description):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/accportprof-{}'.format(pp_name))
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	# build the request using cobra syntax
	infraAccPortP = cobra.model.infra.AccPortP(topMo, ownerKey='', name='{}'.format(pp_name), descr='', ownerTag='')
	infraAccPortP.delete()
	md.reauth()
	commit_mo(md, topMo)		
def Create_access_switch_profile(md,prefix,node_id,pp_name):
	polUni = cobra.model.pol.Uni('')
	infraInfra = cobra.model.infra.Infra(polUni)
	# build the request using cobra syntax
	infraNodeP = cobra.model.infra.NodeP(infraInfra, ownerKey='', name='{}-leaf{}'.format(prefix,node_id), descr='', ownerTag='')
	infraLeafS = cobra.model.infra.LeafS(infraNodeP, ownerKey='', type='range', name='leaf{}'.format(node_id), descr='', ownerTag='')
	infraNodeBlk = cobra.model.infra.NodeBlk(infraLeafS, from_='{}'.format(node_id), name='leaf{}'.format(node_id), descr='', to_='{}'.format(node_id))
	infraRsAccPortP = cobra.model.infra.RsAccPortP(infraNodeP, tDn='uni/infra/accportprof-{}'.format(pp_name))
	md.reauth()
	commit_mo(md, infraInfra)	
def Delete_access_switch_profile(md,prefix,node_id,pp_name):
	polUni = cobra.model.pol.Uni('')
	infraInfra = cobra.model.infra.Infra(polUni)
	# build the request using cobra syntax
	infraNodeP = cobra.model.infra.NodeP(infraInfra, ownerKey='', name='{}-leaf{}'.format(prefix,node_id), descr='', ownerTag='')
	infraNodeP.delete()
	md.reauth()
	commit_mo(md, infraInfra)		
def Create_vpc_switch_profile(md,prefix,node_id,pp_name):
	polUni = cobra.model.pol.Uni('')
	infraInfra = cobra.model.infra.Infra(polUni)
	# build the request using cobra syntax
	infraNodeP = cobra.model.infra.NodeP(infraInfra, ownerKey='', name='{}-leaf{}-{}'.format(prefix,node_id,node_id+1), descr='', ownerTag='')
	infraLeafS = cobra.model.infra.LeafS(infraNodeP, ownerKey='', type='range', name='leaf{}-{}'.format(node_id,node_id+1), descr='', ownerTag='')
	infraNodeBlk = cobra.model.infra.NodeBlk(infraLeafS, from_='{}'.format(node_id), name='leaf{}-{}'.format(node_id,node_id+1), descr='', to_='{}'.format(node_id+1))
	infraRsAccPortP = cobra.model.infra.RsAccPortP(infraNodeP, tDn='uni/infra/accportprof-{}'.format(pp_name))
	md.reauth()
	commit_mo(md, infraInfra)	
def Delete_vpc_switch_profile(md,prefix,node_id,pp_name):
	polUni = cobra.model.pol.Uni('')
	infraInfra = cobra.model.infra.Infra(polUni)
	# build the request using cobra syntax
	infraNodeP = cobra.model.infra.NodeP(infraInfra, ownerKey='', name='{}-leaf{}-{}'.format(prefix,node_id,node_id+1), descr='', ownerTag='')
	infraNodeP.delete()
	md.reauth()
	commit_mo(md, infraInfra)		
def create_pg_pp_sp(md, site,create,brownfield,excel_file,config_file,mynode_id):
	config = ConfigParser.ConfigParser()
	config.read(config_file)
	sp_prefix= config.get("myvars", "SP_PREFIX")
	wb = load_workbook(excel_file,data_only=True)
	polUni = cobra.model.pol.Uni('')
	fabricInst = cobra.model.fabric.Inst(polUni)
	# build the request using cobra syntax
	vpcInstPol = cobra.model.vpc.InstPol(fabricInst, ownerKey='', name='vpc-policy', descr='', ownerTag='', deadIntvl='200')
	if create==0:
		vpcInstPol.delete()
	md.reauth()
	commit_mo(md, fabricInst)
	mynode_id=int(mynode_id)
	for id in range(mynode_id,mynode_id+1):
		sheet_id = id
		sheet_ranges = wb['LEAF{}-{}'.format(sheet_id,sheet_id+1)]
		for line in range (2,100):
			Node_ID=sheet_ranges['A{}'.format(line)].value
			Port=sheet_ranges['B{}'.format(line)].value
			Device=sheet_ranges['C{}'.format(line)].value
			PG_GROUP=sheet_ranges['D{}'.format(line)].value
			Access=sheet_ranges['F{}'.format(line)].value
			UNTAGGED=sheet_ranges['H{}'.format(line)].value
			ALLOWED_VLANs=sheet_ranges['I{}'.format(line)].value
			vPOD=sheet_ranges['K{}'.format(line)].value

			if line==50 or line==51:
				continue		
			aep='{}-leaf{}xx-aep'.format(site,str(sheet_id)[0:1])
			L3_NODE_ID=int(config.get("L3_OUT", "NODE_ID"))
			L3_INT_PORT1=config.get("L3_OUT", "VPC_INT_INTERFACE1")
			L3_INT_PORT2=config.get("L3_OUT", "VPC_INT_INTERFACE2")
			L3_EXT_PORT1=config.get("L3_OUT", "VPC_EXT_INTERFACE1")
			L3_EXT_PORT2=config.get("L3_OUT", "VPC_EXT_INTERFACE2")	
			BB_NODE_ID= int(config.get("BORDER_LEAF", "NODE_ID"))	
			BB_Port1= config.get("BORDER_LEAF", "Port1")
			BB_Port2= config.get("BORDER_LEAF", "Port2")
			if UNTAGGED=='apic':
				aep='csx-ib-mgmt'
			elif sheet_id==L3_NODE_ID and (Port==L3_INT_PORT1 or Port==L3_INT_PORT2 or Port==L3_EXT_PORT1 or Port==L3_EXT_PORT2):
				aep='{}-leaf{}xx-fw-aep'.format(site,str(sheet_id)[0:1])
			elif sheet_id==BB_NODE_ID and (Port=='eth{}'.format(BB_Port1.zfill(2)) or Port=='eth{}'.format(BB_Port2.zfill(2))):
				aep='{}-leaf{}xx-l3-bb-aep'.format(site,str(sheet_id)[0:1])	
			PP_ACCESS_NAME=Create_PP_Access_NAME(site,Node_ID)
			PP_VPC_NAME=Create_PP_VPC_NAME(site,sheet_id)
			PG_ACCESS_NAME=Create_PG_Access_NAME(site,Node_ID,Port)
			PG_VPC_NAME=Create_PG_VPC_NAME(site,sheet_id,Port)
			if Access == 'vpcm':
				PG_VPC_NAME=PG_GROUP
			if Node_ID != None and Device!='SHUTDOWN' and (UNTAGGED !=None or ALLOWED_VLANs !=None):
				SPEED=int(sheet_ranges['J{}'.format(line)].value)
				if create==1:
				    if vPOD==site:
					if UNTAGGED=='apic':
						Create_PG_Access(md,PG_ACCESS_NAME,Device,aep, SPEED)
						Create_access_policy_profile(md,PP_ACCESS_NAME,PG_ACCESS_NAME,Port[3:5],Device)
						Create_access_switch_profile(md,sp_prefix,Node_ID,PP_ACCESS_NAME)						
					# elif UNTAGGED=='span':
						# Create_span_dst(md,Node_ID,Port[3:5])
					elif Access == 'Access':
						Create_PG_Access(md,PG_ACCESS_NAME,Device,aep, SPEED)
						Create_access_policy_profile(md,PP_ACCESS_NAME,PG_ACCESS_NAME,Port[3:5],Device)
						Create_access_switch_profile(md,sp_prefix,Node_ID,PP_ACCESS_NAME)
					elif Access == 'vpc' or Access == 'vpcm':
						Create_vpc_pair(md,sheet_id)
						if sheet_id>200 and sheet_id<300:
							Create_PG_VPC_no_suspend(md,PG_VPC_NAME,Device,aep, SPEED)
						else:	
							Create_PG_VPC(md,PG_VPC_NAME,Device,aep, SPEED)
						Create_vpc_policy_profile(md,PP_VPC_NAME,PG_VPC_NAME,Port[3:5],Device)
						Create_vpc_switch_profile(md,sp_prefix,sheet_id,PP_VPC_NAME)
				elif create==0:
				    if vPOD==site:
					if UNTAGGED=='apic':
						Delete_PG_Access(md,PG_ACCESS_NAME,Device,aep)
						Delete_access_policy_profile(md,PP_ACCESS_NAME,PG_ACCESS_NAME,Port[3:5],Device)
						Delete_access_switch_profile(md,sp_prefix,Node_ID,PP_ACCESS_NAME)
					# elif UNTAGGED=='span':
						# Delete_span_dst(md)						
					elif Access == 'Access':
						Delete_PG_Access(md,PG_ACCESS_NAME,Device,aep)
						Delete_access_policy_profile(md,PP_ACCESS_NAME,PG_ACCESS_NAME,Port[3:5],Device)
						Delete_access_switch_profile(md,sp_prefix,Node_ID,PP_ACCESS_NAME)
					elif Access == 'vpc' or Access == 'vpcm':
						Delete_vpc_pair(md,sheet_id)
						Delete_PG_VPC(md,PG_VPC_NAME,Device,aep)
						Delete_vpc_policy_profile(md,PP_VPC_NAME,PG_VPC_NAME,Port[3:5], Device)
						Delete_vpc_switch_profile(md,sp_prefix,sheet_id,PP_VPC_NAME)	
							
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
	parser.add_argument('-s', '--site', help='Site to Create the APIC.', required=True)
	parser.add_argument('-c', '--create', help='Create Or Delete', required=True)
	parser.add_argument('-b', '--brownfield', help='Brownfield', required=True)
	parser.add_argument('-e', '--excel', help='excel file', required=True)	
	parser.add_argument('-i', '--ini', help='ini file', required=True)	
	parser.add_argument('-n', '--node', help='node id', required=True)	
	args = parser.parse_args()

	print "\n\nArguments received: %s, %s, %s, %s, %s %s %s %s %s\n" % (
		args.apic, args.username, args.password, args.site, args.create, args.brownfield, args.excel, args.ini, args.node)

	# Connect to the APIC and return the APIC MODirectory handle for further processing
	session_token = connect_to_apic(args.apic, args.username, args.password,secure)
	# call the main tenant creation procedure with session token and tenant creation parameters
	if (int(args.node))%2==1:
		create_policy_main_ = create_pg_pp_sp(session_token, args.site, int(args.create), args.brownfield, args.excel, args.ini, args.node)


if __name__ == '__main__':
    main()


