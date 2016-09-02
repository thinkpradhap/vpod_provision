import sys
sys.path.append('../')
from common import *
import yaml


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
def reauth_commit(md,topMo):
        md.reauth()
        commit_mo(md, topMo)

def prov_vlan_pool(md, create, vpod, pool_name, startl=None, endl=None, vlans=None):
        polUni = cobra.model.pol.Uni('')
        infraInfra = cobra.model.infra.Infra(polUni)
        # build the request using cobra syntax
	fvnsVlanInstP = cobra.model.fvns.VlanInstP(infraInfra, ownerKey='', name='{}-vlans'.format(pool_name), descr='', ownerTag='', allocMode='static')
	if create==1:
	    if vlans is None:
		for (start,end) in zip(startl,endl):
			fvnsEncapBlk = cobra.model.fvns.EncapBlk(fvnsVlanInstP, to='vlan-{}'.format(end), from_='vlan-{}'.format(start), allocMode='static')
	    else:			
        	for vlan in vlans:
                	fvnsEncapBlk = cobra.model.fvns.EncapBlk(fvnsVlanInstP, to='vlan-{}'.format(vlan), from_='vlan-{}'.format(vlan), allocMode='static')
	elif create==0:
	    fvnsVlanInstP.delete()

        reauth_commit(md,infraInfra)

def prov_sec_domain(md, create, vpod):
        polUni = cobra.model.pol.Uni('')
        aaaUserEp = cobra.model.aaa.UserEp(polUni)
        # build the request using cobra syntax
        aaaDomain = cobra.model.aaa.Domain(aaaUserEp, ownerKey='', name='{}-sec-domain'.format(vpod), descr='', ownerTag='')
	if create==0:
	    aaaDomain.delete()
        reauth_commit(md,aaaUserEp)

def prov_phy_domain(md, create, vpod, pool_name):
        polUni = cobra.model.pol.Uni('')
        # build the request using cobra syntax
        physDomP = cobra.model.phys.DomP(polUni, ownerKey='', name='{}-phys-dom'.format(vpod), ownerTag='')
	if create==1:
            aaaDomainRef = cobra.model.aaa.DomainRef(physDomP, ownerKey='', name='{}-sec-domain'.format(vpod), descr='', ownerTag='')
            infraRsVlanNs = cobra.model.infra.RsVlanNs(physDomP, tDn='uni/infra/vlanns-[{}-vlans]-static'.format(pool_name))
	elif create==0:
	    physDomP.delete()

        reauth_commit(md,physDomP)

def prov_ext_routed_domain(md, create, dom_name, pool_name):
        polUni = cobra.model.pol.Uni('')
        # build the request using cobra syntax
        l3extDomP = cobra.model.l3ext.DomP(polUni, ownerKey='', name='{}'.format(dom_name), ownerTag='')
	if create==1:
            #aaaDomainRef = cobra.model.aaa.DomainRef(l3extDomP, ownerKey='', name='{}-sec-domain'.format(site), descr='', ownerTag='')
	    if pool_name:
                infraRsVlanNs = cobra.model.infra.RsVlanNs(l3extDomP, tDn='uni/infra/vlanns-[{}-vlans]-static'.format(pool_name))
	elif create==0:
	    l3extDomP.delete()

        reauth_commit(md,l3extDomP)

def prov_aep(md, create, aaep_name, vpod, dom_name):
        polUni = cobra.model.pol.Uni('')
        infraInfra = cobra.model.infra.Infra(polUni)
        # build the request using cobra syntax
        infraAttEntityP = cobra.model.infra.AttEntityP(infraInfra, ownerKey='', name='{}-aep'.format(aaep_name), descr='', ownerTag='')
	if create==1:
	    if dom_name=='{}-phys-dom'.format(vpod):
                 infraRsDomP = cobra.model.infra.RsDomP(infraAttEntityP, tDn='uni/phys-{}'.format(dom_name))
	    else:
		 infraRsDomP = cobra.model.infra.RsDomP(infraAttEntityP, tDn='uni/l3dom-{}'.format(dom_name))
	elif create==0:
	    infraAttEntityP.delete()

        reauth_commit(md,infraInfra)

def prov_vlans_domains_aeps_l2pol(md, create, vpod, filename):
                with open(filename, 'r') as f:
                        parsed_yaml = yaml.load(f)
                vpod_structl = parsed_yaml.get(vpod).get('vlan_pools')
		for vpod_struct in vpod_structl:
                	vlan_pool_name = vpod_struct.get('name')
                	vlansl = vpod_struct.get('vlans')
			vlans_range = vpod_struct.get('vlans_range')
			if vlansl:
				prov_vlan_pool(md, create, vpod, vlan_pool_name, vlans=vlansl)
			if vlans_range:
				start = []
				end = []
				for each in vlans_range:
			    	   for key, value in each.iteritems():
					if key == "start":
				   	    start.append(value)
					else:
				            end.append(value)
				# create vlan pool with range
                		prov_vlan_pool(md, create, vpod, vlan_pool_name, start, end)

		phy_doml = parsed_yaml.get(vpod).get('phy_dom')
		if phy_doml:
		    for phy_dom in phy_doml:
			phy_dom_name = phy_dom.get('name')
			vlanNs = phy_dom.get('vlanNs')
			# create secdom
			prov_sec_domain(md, create, vpod)
			# create physdom
			prov_phy_domain(md, create, vpod, vlanNs)

			aaepl = phy_dom.get('aaep')
			for aaep in aaepl:
			     # create aaep
			     prov_aep(md, create, aaep, vpod, phy_dom_name)

                ext_routed_doml = parsed_yaml.get(vpod).get('ext_routed_dom')
                if ext_routed_doml:
                    for ext_dom in ext_routed_doml:
                        ext_dom_name = ext_dom.get('name')
                        vlanNs = ext_dom.get('vlanNs')
                        # create l3dom
                        prov_ext_routed_domain(md, create, ext_dom_name, vlanNs)

                        aaepl = ext_dom.get('aaep')
                        for aaep in aaepl:
                             # create aaep
                             prov_aep(md, create, aaep, vpod, ext_dom_name)


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
	parser.add_argument('-v', '--vpod', help='Site to Create the APIC.', required=True)
	parser.add_argument('-y', '--yaml', help='yaml file for vlan pools,phys dom, aaep create or delete.', required=True)
        args = parser.parse_args()

        print "\n\nArguments received: %s, %s, %s, %s, %s, %s\n" % (
		args.apic, args.username, args.password, args.create, args.vpod, args.yaml)

        # Connect to the APIC and return the APIC MODirectory handle for further processing

        session_token = connect_to_apic(args.apic, args.username, args.password, secure)
        # call the main tenant creation procedure with session token and tenant creation parameters
        create_policy_main_ = prov_vlans_domains_aeps_l2pol(session_token, int(args.create), args.vpod, args.yaml)

if __name__ == '__main__':
    main()
