#!/usr/bin/python

import subprocess
import argparse
import json 
import time
import csv
import sys
from operator import itemgetter, attrgetter, methodcaller


# Requirements 
## Report must contain max limit per container (cpu and ram).
##      - If max limit is not defined, default request is used 
##	- If default request is not defined, default is used
##	- If default is not defined report -1 (unlimited)
## Report must contain images per container with some way to determine if it is a JBoss or subscription-based image
## Must be able to export to CSV format.  Anything else is nice to have.
## Must support both S2I and manual image builds
## Must be able to timestamp the record (for storing history)
## Must be able to include the provider - As we may have multiple... 

#### OC Client is available at: https://access.redhat.com/downloads/content/290/ver=3.4/rhel---7/3.4.0.39/x86_64/product-software ... Our container will need this client -> We'll also need to add oc login ... 
   ### Need to define process and privileges required for a service account 

#TO FIGURE OUT - How to give a list of systems to connect (with auth tokens?) 

# Assumtions 
## We don't care about pod limits.  Only container limits
## A resource request can not be more than a limit
## If a limit doesn't exist, we will use the request value.  Otherwise we will always use max limit
## We don't care about min limit.  
## A project will not have more than one ResourceQuota - This script does not account for that 
## A project will not have more than one LimitRange - This script does not account for that

# Desired: Make this a pod - php frontend, mysql backend, and python to gather / parse data
  # Run once per day to evaluate data.  Save data indefinitely
  # persistent volume for data 
  # method to export report in csv format (or a nice pdf) would be awesome
  # Have a report to view all projects, their resource quota, and utilization within.  (including builder/deployer pods)
  # Use SHA sums for validation of RedHat limits

# TO TEST
## Do limits always show up in a deployment config?  
## Should we pull from DCs?  Or pods themselves
## If DCs - can we report on replicas and autoscale max pods 

## TODO FOR GREG: 
###### Test RHEL Atomic with Satellite...  
    ## Can it inspect RPMs.  Can it patch it?  Can it deploy it?? 

# Parse Command Line Arguments 
parser = argparse.ArgumentParser()
parser.add_argument("-c", "--csv", help="Write output to a csv file", action='store_true')
args = parser.parse_args()

# Get Run Date/Timestamp
timestamp = time.strftime("%Y-%m-%d %H:%M")

# Output file 
if args.csv:
    csvdir = "/tmp/"
    csvtimestamp = time.strftime("%Y%m%d_%H%M")
    #csvfile = "limits_report." + time.strftime("%Y%m%d_%H%M") + ".csv"
    #f = open(csvdir + csvfile, 'w')

def get_resource(resource_type):
    resource = subprocess.Popen("oc get " + resource_type + " --all-namespaces=true -o json", shell=True, stdout=subprocess.PIPE).stdout.read()
    return json.loads(resource)

def print_table(list, type, sort_by, header_order):
    # sort_by is the order to sort data by 
    # header_order is the order to display headers (if not alphabetic)
    colwidth = {}
    for key in list[0].keys():
        colwidth[key] = max(len(str(dVals[key])) for dVals in list)
        if len(key) > colwidth[key]:
           colwidth[key] = len(key) 
        #print key + ' width is ' + str(colwidth[key])
    
    # Sort list and header
    #sortedlist = sorted(list, key=itemgetter('namespace', 'pod_name', 'container_name'))
    sortedlist = sorted(list, key=itemgetter(*sort_by.split(" ")))
    sortedkeys = sorted(list[0].keys())
    sortlist = header_order.split(" ")
    for i in range(0, len(sortlist)): 
        sortedkeys.insert(0, sortedkeys.pop(sortedkeys.index(sortlist.pop(-1))))
    
    if args.csv:
        csvfile = "limits_report." + csvtimestamp + "." + type + ".csv"
        f = open(csvdir + csvfile, 'w')

    # Print Header and rows 
    header=0
    for row in sortedlist:
        if header == 0:
            if args.csv:
                writer = csv.DictWriter(f, fieldnames=sortedkeys)
                headers = dict( (n,n) for n in sortedkeys )
                writer.writerow(headers)

            printheader = '' 
            for key in sortedkeys:
                printheader += ('|{:' + str(colwidth[key]) + '}').format(key)
            printheader += '|'
            print printheader
            header = 1

        #if args.csv:
        #    writer = csv.writer(f)
        printrow = ''
        for key in sortedkeys:
            #printrow += ("|{" + key + row['" + key + "']:<{width}}").format(row,width=colwidth[key])
            printrow += ('|{:' + str(colwidth[key]) + '}').format(row[key])
        printrow += '|'
        print printrow
        if args.csv:
            csvrow = dict( (key,row[key]) for key in sortedkeys )
            writer.writerow(csvrow)

    if args.csv:
        f.close()


# Get Resources for later usage 
dcjson = get_resource("dc")
imagesjson = get_resource("images")
limitsjson = get_resource("limits")
podsjson = get_resource("pods")
projectsjson = get_resource("projects")
resourcequotasjson = get_resource("resourcequotas")
hpajson = get_resource("hpa")

# Get project resource utilization 
projectkeys = 'project_name cpu_quota memory_quota requests.cpu_quota requests.memory_quota limits.cpu_quota limits.memory_quota pods_quota replicationcontrollers_quota resourcequotas_quota services_quota secrets_quota configmaps_quota persistentvolumeclaims_quota cpu_used memory_used requests.cpu_used requests.memory_used limits.cpu_used limits.memory_used pods_used replicationcontrollers_used resourcequotas_used services_used secrets_used configmaps_used persistentvolumeclaims_used'

projectutil = []
if projectsjson['items'] == []: 
    print 'No Projects Found'
else:
    quotakeys = "cpu memory requests.cpu requests.memory limits.cpu limits.memory pods replicationcontrollers resourcequotas services secrets configmaps persistentvolumeclaims"
    for project in projectsjson['items']:
        projectquota = {}
        for k in projectkeys.split(" "):
            projectquota[k] = '-1'
            projectquota['project_name'] = project['metadata']['name']
        for quota in resourcequotasjson['items']:
            if project['metadata']['name'] == quota['metadata']['namespace']:
                for quotakey in quotakeys.split(" "):
                    if quota['status']['hard'].has_key(quotakey):
                        projectquota[quotakey + '_quota'] = quota['status']['hard'][quotakey]
                        projectquota[quotakey + '_used'] = quota['status']['used'][quotakey]

        # Store projectquota to projectutil
        #print json.dumps(projectquota, sort_keys=True)
        projectutil.append(projectquota)

    # Debug - print projectutil json
    # print json.dumps(projectutil)

    print "############### PROJECT UTILIZATION -", timestamp, "###############"
    print ""
    print_table(projectutil, "project", "project_name", "project_name")

    ### NOTE - Here we would want to run a function to report either to:
      ### DB  (mysql)
      ### CSV (file)
      ### screen - prettytable
      ### We'll want args passed for this or read a config file... 

#### Printing limits that exist... Don't need this for now... 
#print limitsjson['items']
#if limitsjson['items'] == []:
#    print 'No Limits Found'
#else:
#    for rows in limitsjson['items']:
#        #print 'Name:' + rows['metadata']['name']
#        #print 'Namespace:' + rows['metadata']['namespace']
#        print '---------------------'
#        print 'Namespace: ' + rows['metadata']['namespace'] + ' / Limit Name: ' + rows['metadata']['name']
#        for limit in rows['spec']['limits']:
#            #print 'Max CPU / RAM:' + limit['type'] + limit['max']['cpu'] + limit['max']['memory']
#            print limit['type'] + ' max limit: ' + limit['max']['cpu'] + ' cores, ' + limit['max']['memory'] + ' ram'
#    print '---------------------'

# Report on Container Limit Utilization 
podkeys = 'namespace pod_name container_name container_image max_cpu max_memory'

podutil = []

if podsjson['items'] == []:
    print 'No Pods Found'
else: 
    for rows in podsjson['items']:
        for container in rows['spec']['containers']:
            # Get limit for the namespace
            containerlimit = {}
            containerlimit['namespace'] = rows['metadata']['namespace']
            containerlimit['pod_name'] = rows['metadata']['name']
            containerlimit['container_name'] = container['name']
            containerlimit['container_image'] = container['image']
            containerlimit['max_cpu'] = '-1'
            containerlimit['max_memory'] = '-1'
            maxcpu = ''
            maxmemory = ''

            for limitrows in limitsjson['items']:
                if rows['metadata']['namespace'] == limitrows['metadata']['namespace']:
                    for limit in limitrows['spec']['limits']:
                        if limit['type'] == 'Container':
                            if limit.has_key('max'): 
                                if limit['max'].has_key('cpu'):
                                    maxcpu = limit['max']['cpu']
                                if limit['max'].has_key('memory'):
                                    maxmemory = limit['max']['memory']
                            if limit.has_key('defaultRequest'):
                                if limit['defaultRequest'].has_key('cpu') and maxcpu == '':
                                    maxcpu = limit['defaultRequest']['cpu']
                                if limit['defaultRequest'].has_key('memory') and maxmemory == '':
                                    maxmemory = limit['defaultRequest']['memory']
                            if limit.has_key('default'):
                                if limit['default'].has_key('cpu') and maxcpu == '':
                                    maxcpu = limit['default']['cpu']
                                if limit['default'].has_key('memory') and maxmemory == '':
                                    maxmemory = limit['default']['memory']
                    if maxcpu != '': 
                        containerlimit['max_cpu'] = maxcpu
                    if maxmemory != '':
                        containerlimit['max_memory'] = maxmemory

            # Store containerlimit to podutil
            #print json.dumps(containerlimit, sort_keys=True)
            podutil.append(containerlimit)

    # Debug - print podutil json
    #print json.dumps(podutil)
    print ""
    print "############### POD MAXIMUMS -", timestamp, "###############"
    print ""
    print_table(podutil, "pod", "namespace pod_name container_name", "namespace pod_name container_name")



# Report on Deployment Config Utilization
#podkeys = 'namespace pod_name container_name container_image max_cpu max_memory'
#
dcutil = []

if dcjson['items'] == []:
    print 'No Deployment Configs Found'
else:
    for rows in dcjson['items']:
        for row in rows['spec']['template']['spec']['containers']:
            # Get limit for the namespace
            container = {}
            container['namespace'] = rows['metadata']['namespace']
            container['dc_name'] = rows['metadata']['name']
            container['replicas'] = rows['spec']['replicas']
            container['container_name'] = row['name']
            container['container_image'] = row['image']

            if row['resources'].has_key('limits'):
                if row['resources']['limits'].has_key('cpu'):
                    container['max_cpu'] = row['resources']['limits']['cpu']
                if row['resources']['limits'].has_key('memory'):
                    container['max_memory'] = row['resources']['limits']['memory']
            if not container.has_key('max_cpu'):
                container['max_cpu'] = -1
            if not container.has_key('max_memory'):
                container['max_memory'] = -1

            # Get HorizontalPodAutoscaler details 
            container['minReplicas'] = ''
            container['maxReplicas'] = ''
            for hpa in hpajson['items']:
                if hpa['metadata']['namespace'] == rows['metadata']['namespace'] and hpa['metadata']['name'] == rows['metadata']['name']:
                    container['minReplicas'] = hpa['spec']['minReplicas']
                    container['maxReplicas'] = hpa['spec']['maxReplicas']

            # Store container to dcutil
            #print json.dumps(container, sort_keys=True)
            dcutil.append(container)

    # Debug - print podutil json
    #print json.dumps(dcutil)

    print "############### DEPLOYMENT CONFIG UTILIZATION -", timestamp, "###############"
    print ""
    print_table(dcutil, "dc", "namespace dc_name container_name", "namespace dc_name container_name container_image replicas minReplicas maxReplicas max_cpu max_memory")

   # TODO: 
   #  - Calculate max based on limits ... 
   #  - Implement csv option
   #  - Implement mysql option 
   #  - 
