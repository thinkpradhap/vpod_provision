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
def reauth_commit(md,topMo):
	md.reauth()
	commit_mo(md, topMo)
def create_40g(md):
	polUni = cobra.model.pol.Uni('')
	infraInfra = cobra.model.infra.Infra(polUni)
	fabricHIfPol = cobra.model.fabric.HIfPol(infraInfra, ownerKey='', name='40g-port', descr='', ownerTag='', autoNeg='on', speed='40G', linkDebounce='100')
	reauth_commit(md,infraInfra)		
def create_10g(md):
	polUni = cobra.model.pol.Uni('')
	infraInfra = cobra.model.infra.Infra(polUni)
	fabricHIfPol = cobra.model.fabric.HIfPol(infraInfra, ownerKey='', name='10g-port', descr='', ownerTag='', autoNeg='on', speed='10G', linkDebounce='100')
	reauth_commit(md,infraInfra)	
def create_1g(md):
	polUni = cobra.model.pol.Uni('')
	infraInfra = cobra.model.infra.Infra(polUni)
	fabricHIfPol = cobra.model.fabric.HIfPol(infraInfra, ownerKey='', name='1g-port', descr='', ownerTag='', autoNeg='on', speed='1G', linkDebounce='100')
	reauth_commit(md,infraInfra)
def create_bpdu_guard_on(md):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/ifPol-bpdu-guard-on')
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	stpIfPol = cobra.model.stp.IfPol(topMo, ownerKey='', name='bpdu-guard-on', descr='', ctrl='bpdu-guard', ownerTag='')
	reauth_commit(md,topMo)
def create_cdp_on(md):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/cdpIfP-cdp-on')
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	cdpIfPol = cobra.model.cdp.IfPol(topMo, ownerKey='', name='cdp-on', descr='', adminSt='enabled', ownerTag='')
	reauth_commit(md,topMo)
def create_cdp_off(md):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/cdpIfP-cdp-off')
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	cdpIfPol = cobra.model.cdp.IfPol(topMo, ownerKey='', name='cdp-off', descr='', adminSt='disabled', ownerTag='')
	reauth_commit(md,topMo)	
def create_l2_int_policy_global(md):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/l2IfP-l2-int-policy-global')
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	l2IfPol = cobra.model.l2.IfPol(topMo, ownerKey='', name='l2-int-policy-global', descr='', vlanScope='global', ownerTag='')
	reauth_commit(md,topMo)
def create_lacp_active(md):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/lacplagp-lacp-active')
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	lacpLagPol = cobra.model.lacp.LagPol(topMo, ownerKey='', name='lacp-active', descr='', ctrl='fast-sel-hot-stdby,graceful-conv,susp-individual', minLinks='1', maxLinks='16', mode='active', ownerTag='')
	reauth_commit(md,topMo)	
def create_lacp_active_no_supsend(md):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/lacplagp-lacp-active-no-suspend')
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	lacpLagPol = cobra.model.lacp.LagPol(topMo, ownerKey='', name='lacp-active-no-suspend', descr='', ctrl='fast-sel-hot-stdby,graceful-conv', minLinks='1', maxLinks='16', mode='active', ownerTag='')
	reauth_commit(md,topMo)	
def create_lldp_on(md):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/lldpIfP-lldp-on')
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	lldpIfPol = cobra.model.lldp.IfPol(topMo, ownerKey='', name='lldp-on', descr='', adminTxSt='enabled', adminRxSt='enabled', ownerTag='')
	reauth_commit(md,topMo)	
def create_lldp_off(md):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/lldpIfP-lldp-off')
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	lldpIfPol = cobra.model.lldp.IfPol(topMo, ownerKey='', name='lldp-off', descr='', adminTxSt='disabled', adminRxSt='disabled', ownerTag='')
	reauth_commit(md,topMo)	
def delete_40g(md):
	polUni = cobra.model.pol.Uni('')
	infraInfra = cobra.model.infra.Infra(polUni)
	fabricHIfPol = cobra.model.fabric.HIfPol(infraInfra, ownerKey='', name='40g-port', descr='', ownerTag='', autoNeg='on', speed='40G', linkDebounce='100')
	fabricHIfPol.delete()
	reauth_commit(md,infraInfra)	
def delete_10g(md):
	polUni = cobra.model.pol.Uni('')
	infraInfra = cobra.model.infra.Infra(polUni)
	fabricHIfPol = cobra.model.fabric.HIfPol(infraInfra, ownerKey='', name='10g-port', descr='', ownerTag='', autoNeg='on', speed='10G', linkDebounce='100')
	fabricHIfPol.delete()
	reauth_commit(md,infraInfra)
def delete_1g(md):
	polUni = cobra.model.pol.Uni('')
	infraInfra = cobra.model.infra.Infra(polUni)
	fabricHIfPol = cobra.model.fabric.HIfPol(infraInfra, ownerKey='', name='1g-port', descr='', ownerTag='', autoNeg='on', speed='1G', linkDebounce='100')
	fabricHIfPol.delete()
	reauth_commit(md,infraInfra)	
def delete_bpdu_guard_on(md):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/ifPol-bpdu-guard-on')
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	stpIfPol = cobra.model.stp.IfPol(topMo, ownerKey='', name='bpdu-guard-on', descr='', ctrl='bpdu-guard', ownerTag='')
	stpIfPol.delete()
	reauth_commit(md,topMo)
def delete_cdp_on(md):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/cdpIfP-cdp-on')
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	cdpIfPol = cobra.model.cdp.IfPol(topMo, ownerKey='', name='cdp-on', descr='', adminSt='enabled', ownerTag='')
	cdpIfPol.delete()
	reauth_commit(md,topMo)
def delete_cdp_off(md):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/cdpIfP-cdp-off')
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	cdpIfPol = cobra.model.cdp.IfPol(topMo, ownerKey='', name='cdp-off', descr='', adminSt='disabled', ownerTag='')
	cdpIfPol.delete()
	reauth_commit(md,topMo)	
def delete_l2_int_policy_global(md):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/l2IfP-l2-int-policy-global')
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	l2IfPol = cobra.model.l2.IfPol(topMo, ownerKey='', name='l2-int-policy-global', descr='', vlanScope='global', ownerTag='')
	l2IfPol.delete()
	reauth_commit(md,topMo)
def delete_lacp_active(md):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/lacplagp-lacp-active')
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	lacpLagPol = cobra.model.lacp.LagPol(topMo, ownerKey='', name='lacp-active', descr='', ctrl='fast-sel-hot-stdby,graceful-conv,susp-individual', minLinks='1', maxLinks='16', mode='active', ownerTag='')
	lacpLagPol.delete()
	reauth_commit(md,topMo)	
def delete_lacp_active_no_supsend(md):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/lacplagp-lacp-active-no-supsend')
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	lacpLagPol = cobra.model.lacp.LagPol(topMo, ownerKey='', name='lacp-active-no-supsend', descr='', ctrl='fast-sel-hot-stdby,graceful-conv', minLinks='1', maxLinks='16', mode='active', ownerTag='')
	lacpLagPol.delete()
	reauth_commit(md,topMo)	
def delete_lldp_on(md):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/lldpIfP-lldp-on')
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	lldpIfPol = cobra.model.lldp.IfPol(topMo, ownerKey='', name='lldp-on', descr='', adminTxSt='enabled', adminRxSt='enabled', ownerTag='')
	lldpIfPol.delete()
	reauth_commit(md,topMo)	
def delete_lldp_off(md):
	topDn = cobra.mit.naming.Dn.fromString('uni/infra/lldpIfP-lldp-off')
	topParentDn = topDn.getParent()
	topMo = md.lookupByDn(topParentDn)
	lldpIfPol = cobra.model.lldp.IfPol(topMo, ownerKey='', name='lldp-off', descr='', adminTxSt='disabled', adminRxSt='disabled', ownerTag='')
	lldpIfPol.delete()
	reauth_commit(md,topMo)			
def create_vlans_domains_aeps_l2pol(md, create):	
	if create==1:
		create_1g(md)
		create_10g(md)
		create_40g(md)		
		create_bpdu_guard_on(md)
		create_cdp_on(md)
		create_cdp_off(md)
		create_l2_int_policy_global(md)
		create_lacp_active(md)
		create_lacp_active_no_supsend(md)
		create_lldp_on(md)
		create_lldp_off(md)	
	elif create==0:
		delete_1g(md)
		delete_10g(md)
		delete_40g(md)		
		delete_bpdu_guard_on(md)
		delete_cdp_on(md)
		delete_cdp_off(md)
		delete_l2_int_policy_global(md)
		delete_lacp_active(md)
		delete_lacp_active_no_supsend(md)
		delete_lldp_on(md)
		delete_lldp_off(md)			
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
	parser.add_argument('-c', '--create', help='Create Or Delete', required=True)
	args = parser.parse_args()

	print "\n\nArguments received: %s, %s, %s, %s\n" % (
		args.apic, args.username, args.password, args.create)

	# Connect to the APIC and return the APIC MODirectory handle for further processing

	session_token = connect_to_apic(args.apic, args.username, args.password, secure)
	# call the main tenant creation procedure with session token and tenant creation parameters
	create_policy_main_ = create_vlans_domains_aeps_l2pol(session_token, int(args.create))

if __name__ == '__main__':
    main()


