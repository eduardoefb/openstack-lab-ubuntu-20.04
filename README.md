# Define your config file:

Use the example below as reference:
```bash
cat << EOF > config.yml
---

  timezone: Brazil/East
  
  network:
    domain: openstack.int
    ntp_servers:      
      - 0.centos.pool.ntp.org
      - 1.centos.pool.ntp.org
      - 2.centos.pool.ntp.org
      - 3.centos.pool.ntp.org

    oam:
      name: lab_oam
      network: 10.6.0.0
      broadcast: 10.6.0.255
      gateway: 10.6.0.1
      netmask: 255.255.255.0
      netmask_len: 24
      dns: 8.8.8.8
 
    external:
      - name: extnet01
        network: 10.7.0.0        
        broadcast: 10.7.0.255        
        netmask: 255.255.255.0
        netmask_len: 24

      - name: extnet02
        network: 10.8.0.0        
        broadcast: 10.8.0.255        
        netmask: 255.255.255.0
        netmask_len: 24

  nodes:  
    - name: controller01      
      oam_ip: "10.6.0.10"
      role: controller
		
    - name: compute01
      oam_ip: "10.6.0.20"      
      role: compute

    - name: compute02
      oam_ip: "10.6.0.21"      
      role: compute

    - name: compute03
      oam_ip: "10.6.0.22"      
      role: compute

    - name: storage01
      oam_ip: "10.6.0.30"    
      role: storage  

    - name: storage02
      oam_ip: "10.6.0.31"      
      role: storage

  openstack:                
    controller:
      ip: 10.6.0.10
      host: controllervip
      name: controllervip.openstack.int
      
    provider_networks:
      - name: extnet01
        device: eth1
        gateway: 10.7.0.1
        range_begin: 10.7.0.100
        range_end: 10.7.0.200

      - name: extnet02
        device: eth2
        gateway: 10.8.0.1
        range_begin: 10.8.0.100
        range_end: 10.8.0.200        
    
    cinder:
       volume_name: cinder_volumes
       volume_device: sdb    
EOF
```

# Create your enviroment:

You can crete your inventory manually or using the python script, that will extract the nodes from config.yml:

```bash
python3 create_inventory.py config.yml
```

# Start openstack installation:
```bash
time ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook -i hosts create.yml 
```

# Once openstack is installed, execute the following steps to validate the installation (connect to the controller node as root):

1 - Create a private key file:
```bash
ssh-keygen -q -N ""
```
2 - Create a flavor:
```bash
. admin-openrc
openstack flavor create --id 0 --vcpus 1 --ram 64 --disk 1 m1.nano
```

3 - Create a provider network:
```bash
. admin-openrc
openstack network create  --share --external \
  --provider-physical-network extnet01 \
  --provider-network-type flat extnet01

openstack subnet create --network extnet01 \
  --allocation-pool start=10.7.0.100,end=10.7.0.200 \
  --dns-nameserver 8.8.8.8 --gateway 10.7.0.1 \
  --subnet-range 10.7.0.0/24 extnet01  
```

4 - Create the keypair and security group as demo user
```bash
. demo-openrc
openstack keypair create --public-key ~/.ssh/id_rsa.pub mykey
openstack keypair list
openstack security group rule create --proto icmp default
openstack security group rule create --proto tcp --dst-port 22 default
```

5 - Create a provider instance:
```bash
openstack server create --flavor m1.nano --image cirros \
  --nic net-id=`openstack network show extnet01 -c id | grep " id " | awk '{print $4}'` --security-group default \
  --key-name mykey provider-instance
openstack server list  
```

6 - Create a self service networ, router and instance:
```bash
openstack network create selfservice
openstack subnet create --network selfservice \
  --dns-nameserver 8.8.8.8 --gateway 172.31.0.1 \
  --subnet-range 172.31.0.0/24 selfservice
  
openstack router create router
openstack router add subnet router selfservice
openstack router set router --external-gateway extnet01

openstack server create --flavor m1.nano --image cirros \
  --nic net-id=`openstack network show selfservice -c id | grep " id " | awk '{print $4}'` --security-group default \
  --key-name mykey selfservice-instance
openstack server list  
openstack console log show selfservice-instance
```

7 - Create a floating IP and add to self service instance:
```bash
openstack floating ip create extnet01
openstack server add floating ip selfservice-instance 10.7.0.169
openstack server list  
```

8 - Test cinder volumes:
```bash
openstack volume create --size 1 volume1
openstack volume create --size 1 volume2
openstack volume list
openstack server add volume provider-instance volume1
openstack server add volume selfservice-instance volume2
openstack volume list
```

9 - Test heat (orchestration):
```bash

cat << EOF > heat-demo.yml
heat_template_version: 2015-10-15
description: Launch a basic instance with CirrOS image using the
             ``m1.tiny`` flavor, ``mykey`` key,  and one network.

parameters:
  NetID:
    type: string
    description: Network ID to use for the instance.

resources:
  server:
    type: OS::Nova::Server
    properties:
      image: cirros
      flavor: m1.nano
      key_name: mykey
      networks:
      - network: { get_param: NetID }

outputs:
  instance_name:
    description: Name of the instance.
    value: { get_attr: [ server, name ] }
  instance_ip:
    description: IP address of the instance.
    value: { get_attr: [ server, first_address ] }
EOF

export NET_ID=$(openstack network list | awk '/ extnet01 / { print $2 }') && echo $NET_ID
openstack stack create -t heat-demo.yml --parameter "NetID=$NET_ID" stack
openstack stack list
openstack server list
```




10 - Test zun (container):
```bash
. demo-openrc
openstack network list
export NET_ID=$(openstack network list | awk '/ selfservice / { print $2 }') && echo ${NET_ID}
openstack appcontainer run --name cirros --net network=$NET_ID cirros ping 8.8.8.8
openstack appcontainer run --name centos7 --net network=$NET_ID centos:7 ping 8.8.8.8
openstack appcontainer list
openstack appcontainer exec --interactive cirros /bin/sh
openstack appcontainer exec --interactive centos7 /bin/sh
```

Clean:
```bash
openstack appcontainer stop container
openstack appcontainer delete container

openstack appcontainer stop centos7
openstack appcontainer delete centos7
```