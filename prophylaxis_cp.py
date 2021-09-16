__author__ = "ivo hrbacek"
__credits__ = ["ivosh", "laura"]
__version__ = "1.0"
__maintainer__ = "ivo hrbacek"
__email__ = "ihr@actinet.cz"
__status__ = "prod"
__dev_version__ = "v4"
__spec__= "Check Point unused objects, rules with 0 hitcount or old hitcount, OS data"


import requests
import urllib3
import json
import sys
import time
import getpass
import logging
import os
import base64
import re
import datetime


######## Class############
class Connector():
    
    """
    
    Connector class is main class handling connectivity to CP API
    Login is done in constructor once instance of Connector is created
    methods:
            task_method() - help method for publish status check
            publish() - method for changes publishing
            send_cmd() - makes API call based on functionality (viz. API reference)
            logout() - logout form API
            discard() - discard changes
            get_last_status_code() - returns last status code
            run_script - run OS command via mgmt API
    """

    # do not care about ssl cert validation for now   
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


    @classmethod
    def task_method(cls, sid:str, url:str, task:str) -> dict:

        """
        this is help method which is checking task status when publish is needed
        """

        payload_list={}
        payload_list['task-id']=task
        headers = {
            'content-type': "application/json",
            'Accept': "*/*",
            'x-chkp-sid': sid,
        }
        response = requests.post(url+"show-task", json=payload_list, headers=headers, verify=False)
        return response



    def __init__(self, url:str, payload:dict, hitcount_back):

        """
        This is constructor for class, login to API server is handled here - handling also conectivity problems to API
        """

        self.hitcount_back = hitcount_back
        self.sid=""
        # default header without SID
        self.headers_default = {
             'content-type': "application/json",
              'Accept': "*/*",
             }
        # headers for usage in instance methods - with self.SID - will be filled up in constructor
        self.headers = {}
        self.url=url
        self.payload_list = payload # default only username and passowrd
        done=False
        counter=0
        
        # loop to handle connection interuption
        while not done:
            counter +=1
            if counter == 5:
                DoLogging().do_logging ('Connector() - init() - connection to mgmt can not be established even in loop, check your credentials or IP connectivity')
                sys.exit(1)
            try:
                self.response = requests.post(self.url+"login", json=self.payload_list, headers=self.headers_default, verify=False) 
                #print(json.loads(self.response.text))
                if self.response.status_code == 200:
                    #print(json.loads(self.response.text))
                    try:
                        sid_out=json.loads(self.response.text)
                        self.sid = sid_out['sid']
                        self.headers = {
                                'content-type': "application/json",
                                'Accept': "*/*",
                                'x-chkp-sid': self.sid,
                        }
                        DoLogging().do_logging('Connector() - init() - Connection to API is okay')
                        
                    except Exception as e:
                        DoLogging().do_logging(' Connector() - init() - API is not running probably: {}..'.format(e))
                else:
                    a = json.loads(self.response.text)
                    DoLogging().do_logging("Connector() - init() - Exception occured: {}".format(a))
                    
                    
                    if a['message']=='Authentication to server failed.':
                        
                        DoLogging().do_logging ("Connector() - init() - You entered wrong password probably..try it again from the beggining..\n")
                        sys.exit(1)

                    if a['message']=='Administrator is locked.':
                       
                        DoLogging().do_logging ("Connector() - init() - Use this command to unlock admin:\n")
                        DoLogging().do_logging ("Connector() - init() - mgmt_cli -r true unlock-administrator name 'admin' --format json -d 'System Data'")
                        sys.exit(1)

                    DoLogging().do_logging('Connector() - init() - There is no SID, connection problem to API gateway, trying again..')
                    time.sleep (5)
                    continue
            except requests.exceptions.RequestException as e:   
                DoLogging().do_logging(' Connector() - init() - exception occured..can not connect to mgmt server, check IP connectivity or ssl certificates!!!')     
            else:
                done=True
                
                
                
    def get_hitcount_back(self):
        """
        return number of days when hitcount will be counted
        
        """
        DoLogging().do_logging(' Connector() - get_hitcount_back() checking hitcount back number')     
        try:
            int(self.hitcount_back)
            return self.hitcount_back
        except Exception as e:
            print ("Insert decimal number for hitcount back number, leaving")
            DoLogging().do_logging(' Connector() - get_hitcount_back() - hitcount back is not decimal number, can not continue') 
            self.logout()
            sys.exit(1)
            
        


    def publish(self):

        """
        Publish method is responsible for publishing changes to mgmt server, its here for future usage, its not used now by rulerevision
        """

        payload_list={}
        headers = {
            'content-type': "application/json",
            'Accept': "*/*",
            'x-chkp-sid': self.sid,
        }

        done=False
        counter=0
        
        while not done:
            counter +=1
            if counter == 5:
                DoLogging().do_logging ('Connector() - publish() - connection to mgmt for publish does not work even in loop.. exit')
                sys.exit(1)
            try:
                self.response = requests.post(self.url+"publish", json=payload_list, headers=headers, verify=False)
                publish_text=json.loads(self.response.text)
                #print (publish_text)
                show_task=Connector.task_method(self.sid,self.url,publish_text['task-id'])
                show_task_text = json.loads(show_task.text)
                
                while show_task_text['tasks'][0]['status'] == "in progress":
                    DoLogging().do_logging ("Connector() - publish() - publish status = ", show_task_text['tasks'][0]['progress-percentage'])
                    time.sleep(10)
                    show_task=Connector.task_method(self.sid,self.url,publish_text['task-id'])
                    show_task_text=json.loads(show_task.text)
                    DoLogging().do_logging (" Connector() - publish() - publish status = ", show_task_text['tasks'][0]['progress-percentage'] , show_task_text['tasks'][0]['status'])
                    

                DoLogging().do_logging ('Connector() - publish() - publish is done')
                return self.response
            except:   
                DoLogging().do_logging(' Connector() - publish() - exception occured..can not connect to mgmt server when publishing, check IP connectivity!!!')     
            else:
                done=True



    def logout(self):

        """
        Logout method for correct disconenction from API

        """

        done=False
        counter=0
        while not done:
            counter +=1
            if counter == 5:
                DoLogging().do_logging('Connector() - logout() - logout can not be done because connection to mgmt is lost and reconnect does not work...')
                sys.exit(1)
                
            else:
                try:
                    payload_list={}
                    self.response = requests.post(self.url+"logout", json=payload_list, headers=self.headers, verify=False)
                    if self.response.status_code == 200:
                        DoLogging().do_logging ('Connector() - logout() - logout from API is okay')
                        return self.response.json()
                    else:
                        out = json.loads(self.response.text)
                        DoLogging().do_logging (" ")
                        DoLogging().do_logging(out)
                        DoLogging().do_logging (" ")
                        return self.response.json()
                    
                except:
                   DoLogging().do_logging ('Connector() - logout() - connection to gateway is broken, trying again')
                else:
                    done=True
           
                     

    def send_cmd(self, cmd, payload):

        """
        Core method, all data are exchanged via this method via cmd variable, you can show, add data etc.
        """

        done=False
        counter=0
        while not done:
            counter +=1
            if counter == 5:
                DoLogging().do_logging ("Connector() - send_cmd() - Can not send API cmd in loop, there are some problems, changes are unpublished, check it manually..")
                self.discard()
                self.logout()
                sys.exit(1)
            else:
                 try:
                     payload_list=payload
                     self.response = requests.post(self.url + cmd, json=payload_list, headers=self.headers, verify=False)
                     if self.response.status_code == 200:
                         #uncomment for TSHOOT purposes
                         #DoLogging().do_logging ('Connector() - send_cmd() - send cmd is okay')
                         #out = json.loads(self.response.text)
                         #DoLogging().do_logging ('Connector() - send_cmd() - send cmd response is 200 :{}'.format(out))
                         return self.response.json()
                     else:
                         out = json.loads(self.response.text)
                         DoLogging().do_logging(" Connector() - send_cmd() - response code is not 200 :{}".format(out))
                         return self.response.json()
                     
                     
                 except:
                    DoLogging().do_logging ("Connector() - send_cmd() - POST operation to API is broken due connectivity flap or issue.. trying again..")
                    
                 else:
                    done=True


    def discard(self):

        """
        discard method for correct discard of all data modified via API

        """

        done=False
        counter=0
        while not done:
            counter +=1
            if counter == 5:
                DoLogging().do_logging('Connector() - discard() - discard can not be done because connection to mgmt is lost and reconnect does not work...')
                sys.exit(1)
                
            else:
                try:
                    payload_list={}
                    self.response = requests.post(self.url+"discard", json=payload_list, headers=self.headers, verify=False)
                    if self.response.status_code == 200:
                        DoLogging().do_logging ('Connector() - discard() - discard is okay')
                        out = json.loads(self.response.text)
                        DoLogging().do_logging("Connector() - discard() - response code 200: {}".format(out))
                        return self.response.json()

                    else:
                        out = json.loads(self.response.text)
                        DoLogging().do_logging("Connector() - discard() - response code is not 200: {}".format(out))
                        return self.response.json()
                except:
                   DoLogging().do_logging ('Connector() - discard() - discard - connection to gateway is broken, trying again')
                else:
                    done=True
                    
    @staticmethod
    def base64_ascii(base64resp):
        """Converts base64 to ascii for run command/showtask."""
        try:
            return base64.b64decode(base64resp).decode('utf-8')
        except Exception as e:
            DoLogging().do_logging("base64 error:{}".format(e))
    
                    
                    
    def run_script(self, payload):
        
        """
        run script method is responsible for running script on target (ls -la, df -lh etc. basic linux commands)
        """

        payload_list=payload
        headers = {
            'content-type': "application/json",
            'Accept': "*/*",
            'x-chkp-sid': self.sid,
        }

        
        return_string = ''
        
        done=False
        counter=0
        
        while not done:
            counter +=1
            if counter == 5:
                DoLogging().do_logging('Connector() - run_script() - discard can not be done because connection to mgmt is lost and reconnect does not work...')
                sys.exit(1)
                
            else:
                try:    
                      
                    self.response = requests.post(self.url+"run-script", json=payload_list, headers=headers, verify=False)
                    tasks=json.loads(self.response.text)
                    for item in tasks['tasks']:
                        while True:
                            show_task=Connector.task_method(self.sid,self.url,item['task-id'])
                            show_task_text=json.loads(show_task.text)
                            DoLogging().do_logging ("Connector() - run_script() - :{}".format(show_task_text))
                            time.sleep (10)
                            if show_task_text['tasks'][0]['progress-percentage'] == 100:
                                base64resp = (str(self.send_cmd('show-task', payload={"task-id":show_task_text['tasks'][0]['task-id'], "details-level":"full"})['tasks'][0]['task-details'][0]['responseMessage']))
                                asciiresp = self.base64_ascii(base64resp)
                                return_string=return_string+"\n\n"+"Data for target:"+item['target']+"\n"+asciiresp+"\n\n\n\n\n\n"
                                DoLogging().do_logging ("Connector() - run_script() - :{}".format(show_task_text))
                                break
                            else:
                                continue
                        
                        
                    return return_string
                        
                except Exception as e:
                    DoLogging().do_logging ("Connector() - run_script() - Exception in run_script method, some data not returned, continue: {} {}".format(e, tasks))
                else:
                    done=True
         
         
                    
            
######## Class############                  
class GetUnused():
    
    """
    class for geting all unused data from mgmt

    """



    def __init__(self, connector:object):

        """
        constructor has just instance of connector and default json payload for API - offset and limit are than incremented based on data which are on API server
        """

        self.connector = connector
        self.offset = 0
        self.counter = 0

        self.payload_rules ={
        "limit" : 500,
        "offset" : self.offset,
        "details-level" : "full",
        }
        DoLogging().do_logging('GetUnused()__init__ - constructor loaded sucessfully')
        
    
    def get_counter(self):
        DoLogging().do_logging('GetUnused() - get_counter() - returning unused object counter')
        return self.counter
        

    def get_unused(self) -> list:

        """
        get all unused objects

        """
        
        result_list = []
        
        result = self.connector.send_cmd('show-unused-objects', self.payload_rules) # whole rulebase for particular layer
        DoLogging().do_logging('GetUnused()__get_unused() - first iteration of getting data finished sucessfully')
        help_list=result['objects']
        for item in help_list:    
            result_list.append(item)
        
        try:

            while result['to'] != result['total']: # if there are many rules, do cycle with offset +100 and hangle all data in rulebase
                
                self.offset += 500
                payload_rules02 ={
                    "limit" : 500,
                    "offset" : self.offset,
                    "details-level" : "full"
                }
                
                
                result = self.connector.send_cmd('show-unused-objects', payload_rules02) # add result to existing dict
                DoLogging().do_logging("GetUnused()__get_unused() - other iteration of getting data finished sucessfully")
                help_list=result['objects']
                for item in help_list:    
                    result_list.append(item)
                result_list.append(item)
                
        except KeyError:
            pass
            
        DoLogging().do_logging('GetUnused()__get_unused() - counting all unused objects')
        for item in result_list:
            self.counter=self.counter+1
            
            
        DoLogging().do_logging('GetLayers()__get_unused() - going to return data')
        return result_list
    
    
    
######## Class############
class GetLayers():

    """
    class for geting all layers from mgmt server

    """

    def __init__(self, connector:object, domain:str):

        """
        constructor has just instance of connector and default json payload and info about domain
        """

        self.connector = connector
        self.payload_layers ={
        "limit" : 500,
        "offset" : 0,
        "details-level" : "standard"
        }
        DoLogging().do_logging('GetLayers()__init__ - constructor loaded sucessfully')
        self.domain=domain

    

    def get_layers(self) -> list:

        """
        get all layers and save name and uid to list - values are tuples

        for getting name use just:
            for item in all_layers:
                print (item[0])

        """

        all_layers = []

        if self.domain=="Global":
            layers = self.connector.send_cmd('show-access-layers', self.payload_layers)
            for layer in layers['access-layers']:
                all_layers.append((layer['name'], layer['uid']))

            DoLogging().do_logging('GetLayers()__get_layers() - going to return data for mds global layers only {0}'.format(all_layers))


        else:
            DoLogging().do_logging('GetLayers()__get_layers() - calling Connector')
            layers = self.connector.send_cmd('show-access-layers', self.payload_layers)
            # print (layers)
            
            for layer in layers['access-layers']:
                DoLogging().do_logging('GetLayers()__get_layers() - processing layer: {}'.format(layer["name"]))
                if (layer['domain']['domain-type']) == "global domain":
                    # print ("no global domain added")
                    pass
                else:
                    all_layers.append((layer['name'], layer['uid']))
                   
            
            DoLogging().do_logging('GetLayers()__get_layers() - going to return data for no mds layers {0}'.format(all_layers))

        
        return all_layers
        


    def get_layer(self, uid) -> dict:
        DoLogging().do_logging('GetLayers()__get_layers() - calling Connector')
        layer = self.connector.send_cmd('show-access-layer', uid)
        DoLogging().do_logging('GetLayers()__get_layer() - going to return data {0}'.format(layer))
        return layer
 
 
                    
######## Class############              
class GetRulebase():
    
    """
    class for geting all data from particular layer

    """



    def __init__(self, connector:object, layer:str=None, uid:str=None):

        """
        constructor has just instance of connector and default json payload for API - offset and limit are than incremented based on data which are on API server
        """

        self.connector = connector
        self.layer = layer
        self.uid = uid
        self.offset = 0

        self.payload_rules ={
        "limit" : 500,
        "offset" : self.offset,
        "name" : self.layer,
        "uid": self.uid,
        "details-level" : "standard",
        "show-as-ranges" : "false",
        "use-object-dictionary" : "true", # this adding to rulebase also objects data
        "show-hits": "true"
        }
        DoLogging().do_logging('GetRulebase()__init__ - constructor loaded sucessfully')



    def get_rulebase(self) -> list:

        """
        get all rules in iterations, using offset and limit for large rulebases

        """
        
        result_rulebase_list = []
        
        result_rulebase = self.connector.send_cmd('show-access-rulebase', self.payload_rules) # whole rulebase for particular layer
        DoLogging().do_logging('GetRulebase()__get_rulebase() - first iteration of getting data finished sucessfully')
        result_rulebase_list.append(result_rulebase)
        
        try:

            while result_rulebase['to'] != result_rulebase['total']: # if there are many rules, do cycle with offset +100 and hangle all data in rulebase
                
                self.offset += 500
                payload_rules02 ={
                    "limit" : 500,
                    "offset" : self.offset,
                    "name" : self.layer,
                    "uid": self.uid,
                    "details-level" : "standard",
                    "show-as-ranges" : "false",
                    "use-object-dictionary" : "true",
                    "show-hits": "true"
                }
                
                
                result_rulebase = self.connector.send_cmd('show-access-rulebase', payload_rules02) # add result to existing dict
                DoLogging().do_logging('GetRulebase()__get_rulebase() - other iteration of getting data finished sucessfully')
                result_rulebase_list.append(result_rulebase)
                
        except KeyError as e:
            DoLogging().do_logging('GetRulebase()__get_rulebase() - Key Error: {}'.format(e))
            pass
            
        DoLogging().do_logging('GetRulebase()__get_rulebase() - going to return data for no mds layers {0}'.format(self.layer))
        return  result_rulebase_list



######## Class############
class DoLogging():
    
    """
    Logging class, to have some possibility debug code in the future

    """

    def __init__(self):

        """
        Constructor does not do anything
        """
        pass
      

    def do_logging(self, msg:str):

        """
        Log appropriate message into log file
        """
        # if needed change to DEBUG for more data
        logging.basicConfig(filename="logcp.elg", level=logging.INFO)
        logging.info(msg)


######## Class############     
class ShowGroup():
    
    """
    Class handling data for groups, returning only members of groups
    """

    def __init__(self, uid, connector:object):
    
        """
        constructor has just instance of connector and default json payload
        """

        self.connector = connector
        self.uid = uid

        self.payload = {
            'uid': self.uid
        }
      

    def show_group_members(self):
        
        """
        return members for netwowrk group
        """
        
        group_data = self.connector.send_cmd('show-group', self.payload)
        return group_data['members']


    def show_service_group_members(self):
        
        """
        return members for service group
        """

        group_data = self.connector.send_cmd('show-service-group', self.payload)
        return group_data['members']

    
    def show_app_site_group_members(self):

        """
        return members for app group
        """

        group_data = self.connector.send_cmd('show-application-site-group', self.payload)
        return group_data['members']
        

 
#############################METHODS##################################

     
                    
def ask_for_question():
    
        """
        handle user input at the beginning

        """

        try:

            print("###############################",
                
                "CP profylassó v1",
                
                
                "returing those data:\n\nunused objects, rules with zero hitcount, rules where hitcount is older than X days[script will ask you how many days], disabled rules, basic OS data.. ",
                
                "running also scripts remotely via API (doctor-log.sh, make sure scripts are presented in /var/tmp on target system)",
        
                "If you wanna add new command, just go to method main() and follow comments, or if you wanna add target exception to avoid running OS command go to def get_targets_data() method and add target to exception list, all OS commands are by default commented",
                
                "###############################",
                sep="\n\n")

            
            user=input("Enter API/GUI user name with write permissions: ")
            password=getpass.getpass()
            server_ip=input("Enter server IP: ")
            hitcount_before=input("Enter number of days for hitcount verificaton - example: 30 -> rules where hitcount is older than 30 days are goint to be saved: ")
            
            print ("")
           

            if not user or not password or not server_ip:
                print ("Empty username or password or server IP, finish..")
                sys.exit(1)
            else:
                payload ={
                    "user":user,
                    "password":password
                }
                connector = Connector('https://{}/web_api/'.format(server_ip), payload, hitcount_before)
                return connector


        except KeyboardInterrupt:
            print ("\n ctrl+c pressed, exit..")
            sys.exit(1)
        except Exception as e:
            print ("Error in ask question method, leaving")
            sys.exit(1)
            
             




def handle_unused_objects(connector):
    """
    get unused object from mgmt machine
    
    """
  
        
    try:    
        current_path=(os.path.dirname(os.path.abspath(__file__)))
        data_folder='{0}/data/rules_and_objects'.format(current_path)
        unused_file='{0}/unused_objects.txt'.format(data_folder)
        unused = GetUnused(connector)
        with open(unused_file, 'w') as outfile:
            #json.dump(unused.get_unused(), outfile, sort_keys=False)
            unused_objects=unused.get_unused()
            print('saving unused objects, count is:{}\n\n'.format(unused.get_counter())+'\n\n'.join('{}'.format(item)for item in unused_objects), file=outfile) 
            DoLogging().do_logging('saving unused objects, count is : {}'.format(unused.get_counter()))
            
    except Exception as e:
        DoLogging().do_logging('problem in handle_unused_objects(): {}'.format(e))
        connector.logout()
        sys.exit(1)
        
        
        
        
    

def get_targets_data(connector, mapping_list):
    """
    get basic OS data from all targets connected to mgmt machine
    """
    try:
        
        targets=connector.send_cmd('show-gateways-and-servers', payload={})['objects']
        target_list = []
        
        """
        if you want to exclude some targets, just add name here in exceptions
        """
        
        exceptions = ['aa', 'fw-cluster']
        
        for item in targets:
            is_there=False
            for item02 in exceptions:
                if item02 == item['name']:
                    is_there=True
                    break
            if is_there == False:
                target_list.append(item['name'])
                
        print ("targets connected to specified mgmt machine:{}".format(target_list))
        DoLogging().do_logging("targets:{}".format(target_list))
                    
        DoLogging().do_logging("\n get_targets_data() - staring..supported commands:\n{}".format(mapping_list))

        # go through list of dicts and map key and value to right possitions
        for item in mapping_list:
            # map key and value - data filed in json and appropriate command for API
            for script_name, command in item.items() :
                # if JSON is empty with data - its emty list od dicts
                
                payload={
                "script-name": script_name,
                "script":command,
                "targets":target_list
                }
                
                print ("script_name:{}\n script:{}\n\n".format(payload['script-name'], payload['script']))
        
                
                current_path=(os.path.dirname(os.path.abspath(__file__)))
                data_folder='{0}/data/OS'.format(current_path)
                output_file='{0}/{1}.txt'.format(data_folder, script_name)
                
                with open(output_file, 'w') as outfile:
                    #json.dump(unused.get_unused(), outfile, sort_keys=False)
                    print (connector.run_script(payload),file=outfile) 
                    DoLogging().do_logging('get_targets_data() - saving commands for script name:{}'.format(script_name))
                    
    except Exception as e:
        DoLogging().do_logging('problem in get_targets_data():{}'.format(e))
        connector.logout()
        sys.exit(1)

                
def folders():
    """
    define folde for data files
    """
    
    
    current_path=(os.path.dirname(os.path.abspath(__file__)))
    
    data='{0}/data'.format(current_path)
    dataOS='{0}/data/OS'.format(current_path)
    data_objects='{0}/data/rules_and_objects'.format(current_path)
    
    access_rights = 0o755


    if os.path.exists(data) :
        
        DoLogging().do_logging('folders() - directories exist')

    else:
        try: 
            os.mkdir(data, access_rights)
            os.mkdir(dataOS, access_rights)
            os.mkdir(data_objects, access_rights)
        except OSError:  
            DoLogging().do_logging('folders() - directory cpdata_single probably exist')
            sys.exit(1)
        else:  
            DoLogging().do_logging('folders() - directory cpdata_single created successfully ')



    
def get_real_uid_data(rule:list, objects_dictionary:list, connector:object) -> dict:

    DoLogging().do_logging('librcp_reviewrules.py__ReviewRules()._get_real_uid_data - entering method to get real UID data')
    
    filtered_objects ={}

    src_all = []
    dst_all = []
    srv_all = []
    trg_all = []

    if 'name' in rule:
        name = rule['name']
    else:
        name = ''
    if 'inline-layer' in rule:
        inline = rule['inline-layer']
    else:
        inline = None     
    num = rule['rule-number']
    src = rule['source']
    dst = rule['destination']
    srv = rule['service']
    act = rule['action']
    hits = rule['hits']
    if rule['track']['type']:
        trc = rule['track']['type']
    else:
        trc = rule['track']
    trg = rule['install-on']
    
    DoLogging().do_logging('librcp_reviewrules.py__ReviewRules()._get_real_uid_data - handling object dictionary')
    for obj in objects_dictionary:  
        if name == obj['uid']:
            name = obj['name']
        if num == obj['uid']:
            num = obj['name']
        if act == obj['uid']:
            act = obj['name']
        if trc == obj['uid']:
            trc = obj['name']
        if inline == obj['uid']:
            inline = obj['name']
            

    """
    #handle all src/dst/srvc and compare them to object dictionary and save them
    """    

    try:

        DoLogging().do_logging('librcp_reviewrules.py__ReviewRules()._get_real_uid_data - handling sources')
        for srcobj in src:
            for obj in objects_dictionary: 
                if srcobj == obj['uid']:
                    if obj['type'] == 'group':
                        DoLogging().do_logging('librcp_reviewrules.py__ReviewRules()._get_real_uid_data - group is present, aditional call to get group members')
                        check_group = ShowGroup(obj['uid'], connector)
                        for item in check_group.show_group_members():
                            if 'ipv4-address' in item:
                                src_all.append({"name":item['name'], "ip":str(item['ipv4-address'])+'/32', "type":"host"})
                            elif 'subnet4' in item:
                                src_all.append({"name":item['name'], "ip":str(item['subnet4'])+'/'+ str(item['mask-length4']), "type":"network"})  
                            elif item['type'] =='CpmiAnyObject':
                                src_all.append({"name":item['name'], "type":item['type'], "ip":"any"})
                            elif item['type'] =='address-range':
                                src_all.append({"name":item['name'], "first-ip":item['ipv4-address-first'],"last-ip":item['ipv4-address-last'], "type":"range"})
                            else:
                                src_all.append({"name":item['name'], "general":item['type'], "type":"pass"}) 

                    elif obj['type'] =='CpmiAnyObject':
                        src_all.append({"name":obj['name'], "type":obj['type'], "ip":"any"})
                    elif obj['type'] =='address-range':
                        src_all.append({"name":obj['name'], "first-ip":obj['ipv4-address-first'], "last-ip":obj['ipv4-address-last'], "type":"range"})
                    elif 'ipv4-address' in obj:
                        src_all.append({"name":obj['name'], "ip":str(obj['ipv4-address'])+'/32', "type":"host"})
                    elif 'subnet4' in obj:
                        src_all.append({"name":obj['name'], "ip":str(obj['subnet4'])+'/'+ str(obj['mask-length4']),"type":"network"})
                    else:
                        src_all.append({"name":obj['name'], "general":obj['type'], "type":"pass"})  
        DoLogging().do_logging('librcp_reviewrules.py__ReviewRules()._get_real_uid_data - handling destinations')                                        
        for dstobj in dst:
            for obj in objects_dictionary:
                if dstobj == obj['uid']:
                    if obj['type'] == 'group': 
                        DoLogging().do_logging('librcp_reviewrules.py__ReviewRules()._get_real_uid_data - group is present, aditional call to get group members')
                        check_group = ShowGroup(obj['uid'], connector)
                        for item in (check_group.show_group_members()):
                            if 'ipv4-address' in item:
                                dst_all.append({"name":item['name'], "ip":str(item['ipv4-address'])+'/32', "type":"host"})
                            elif 'subnet4' in item:
                                dst_all.append({"name":item['name'], "ip":str(item['subnet4'])+'/'+str(item['mask-length4']),"type":"network"}) 
                            elif item['type'] =='CpmiAnyObject':
                                dst_all.append({"name":item['name'], "type":item['type'], "ip":"any"})
                            elif item['type'] =='address-range':
                                dst_all.append({"name":item['name'], "first-ip":item['ipv4-address-first'], "last-ip":item['ipv4-address-last'], "type":"range" })
                            else:
                                dst_all.append({"name":item['name'],"general":item['type'],"type":"pass"})
                    elif obj['type'] =='CpmiAnyObject':
                        dst_all.append({"name":obj['name'], "type":obj['type'], "ip":"any"})
                    elif obj['type'] =='address-range':
                        dst_all.append({"name":obj['name'], "first-ip":obj['ipv4-address-first'], "last-ip":obj['ipv4-address-last'], "type":"range"})
                    elif 'ipv4-address' in obj:
                        dst_all.append({"name":obj['name'], "ip":str(obj['ipv4-address'])+'/32', "type":"host"})
                    elif 'subnet4' in obj:
                        dst_all.append({"name":obj['name'], "ip":str(obj['subnet4'])+'/'+ str(obj['mask-length4']),"type":"network"})
                    else:
                        dst_all.append({"name":obj['name'], "general":obj['type'], "type":"pass"})                        
        DoLogging().do_logging('librcp_reviewrules.py__ReviewRules()._get_real_uid_data - handling services')
        for srvobj in srv:
            for obj in objects_dictionary:
                if srvobj == obj['uid']:
                    if obj['type'] == 'service-group': 
                        DoLogging().do_logging('librcp_reviewrules.py__ReviewRules()._get_real_uid_data - service group is present, aditional call to get group members')
                        check_group = ShowGroup(obj['uid'], connector)
                        for item in (check_group.show_service_group_members()):
                            if 'port' in item:    
                                srv_all.append({"name":item['name'], "port":item['port'], "type":item['type']})
                            else: 
                                srv_all.append({"name":item['name'], "type":"pass"})
                                
                    elif obj['type'] == 'application-site-group':
                        DoLogging().do_logging('librcp_reviewrules.py__ReviewRules()._get_real_uid_data - app site group is present, aditional call to get group members')
                        check_group = ShowGroup(obj['uid'], connector)
                        for item in (check_group.show_app_site_group_members()):
                            if item['type']=='application-site':
                                srv_all.append({"name":item['name'], "type":"pass"})
                            elif item['type']=='application-site-category':
                                srv_all.append({"name":item['name'], "type":"pass"})
                            else:
                                srv_all.append({"name":item['name'], "general":item['type'], "type":"pass"})

                    elif obj['type']=='service-other':
                        srv_all.append({"name":obj['name'],"type":"service-other"})  
                    elif obj['type']=='service-icmp':
                        srv_all.append({"name":obj['name'], "type":"service-icmp"})

                    elif obj['type']=='CpmiAnyObject':
                        srv_all.append({"name":obj['name'], "type":"CpmiAnyObject"}) 
                    elif obj['type']=='application-site':
                        srv_all.append({"name":obj['name'], "type":"pass"}) 
                    elif obj['type']=='application-site-category':
                        srv_all.append({"name":obj['name'], "type":"pass"})                           
                    else:
                        if 'port' in obj:
                            DoLogging().do_logging('librcp_reviewrules.py__ReviewRules()._get_real_uid_data - there is port range, split needed')
                            srv_all.append({"name":obj['name'], "port":obj['port'], "type":obj['type']}) 
                        else: 
                            srv_all.append({"name":obj['name'], "general":obj['type'],"type":"pass" })      

        DoLogging().do_logging('librcp_reviewrules.py__ReviewRules()._get_real_uid_data - handling targets')
        for trgobj in trg:
            for obj in objects_dictionary:
                if trgobj == obj['uid']:
                    trg_all.append((obj['name']))


    except Exception as e:
        DoLogging().do_logging('librcp_reviewrules.py__ReviewRules()._get_real_uid_data - problems with keys when handling real object data : {}'.format(e))
        connector.logout()
        sys.exit(1)

    """
    #update list of rules and send back 
    """
    DoLogging().do_logging('librcp_reviewrules.py__ReviewRules()._get_real_uid_data - updating filtered_objects for return ')
    filtered_objects.update({
        'source': src_all,
        'source-negate': rule['source-negate'],
        'destination': dst_all,
        'destination-negate': rule['destination-negate'],
        'service': srv_all,
        'service-negate': rule['service-negate'],
        'action': act,
        'inline-layer': inline,
        'hits':hits,
        'track': trc,
        'target': trg_all,
        
    })
    uncoment = "if you wanna see data, modify the code in get_real_uid_data() method - remove uncomment variable with filtered_objects in DoLogging "
    DoLogging().do_logging('librcp_reviewrules.py__ReviewRules()._get_real_uid_data - leaving method to return real UID data:\{}'.format(uncoment))
    return (filtered_objects)



def _handle_hitcount_and_any(connector, all_rules_real):
    
    hitcount_back=connector.get_hitcount_back()
    date_format = '\d{4}-\d{2}-\d{2}'
    current_date = str(datetime.date.today())
    date_back=str(datetime.date.today() + datetime.timedelta(-int(hitcount_back)))
    
    zero_hitcount = []
    older_hitcount = []
    any_object = []
    disabled_rules = []
    
    zero_counter = 0
    older_counter = 0
    any_counter = 0
    disabled_rules_count = 0
    
    
    for item in all_rules_real:
        if bool(item['enabled'])== False:
            disabled_rules.append(item)
            disabled_rules_count=disabled_rules_count+1
        
        try:
            last_date_raw = item['rule_objects']['hits']['last-date']['iso-8601']
        except:
            DoLogging().do_logging ("handle_hitcount() - zero hitcount for rule:\n{}\n".format(item['original_rule_id']))
            zero_hitcount.append(item)
            zero_counter= zero_counter+1
            if item['rule_objects']['source'][0]['type']=="CpmiAnyObject" or item['rule_objects']['destination'][0]['type']=="CpmiAnyObject" or item['rule_objects']['service'][0]['type']=="CpmiAnyObject":
                any_object.append(item)
                any_counter=any_counter+1 
        else:
            last_date=re.search(date_format, last_date_raw).group()
            DoLogging().do_logging ("handle_hitcount() - today is: {} last hitcount at : {} for rule:\n{}".format(current_date,last_date,item['original_rule_id']))
            if last_date < date_back:
                DoLogging().do_logging ("handle_hitcount() - match, rule hitcount is older than {} days({})\n".format(hitcount_back,date_back))
                older_hitcount.append(item)
                older_counter=older_counter+1
                if item['rule_objects']['source'][0]['type']=="CpmiAnyObject" or item['rule_objects']['destination'][0]['type']=="CpmiAnyObject" or item['rule_objects']['service'][0]['type']=="CpmiAnyObject":
                    any_object.append(item)
                    any_counter=any_counter+1 
            
                
        
            
            
    return {"disabled":disabled_rules, "disabled_counter":disabled_rules_count,"zero":zero_hitcount,"old":older_hitcount, "any":any_object, "zero_counter":zero_counter, "old_counter":older_counter, "any_counter":any_counter}
            
        
    
    
def handle_rules(connector):
    
    
    DoLogging().do_logging("\n handle_rules() - statring, only single domain mgmt is now supported..")
    layers = GetLayers(connector, "SMC User") 
    
    #go via all layers aka policies
    for item in layers.get_layers():
        # proces every layer
        
        layer_name = item[0]
        layer_uid = item[1]
        get_rulebase = GetRulebase(connector, None, layer_uid)
        rules = get_rulebase.get_rulebase()
        all_rules_real = []
        for rule in rules:
            #print (rule)
            dict_tmp_rule ={}
            if 'rulebase' in rule:
                for item in rule['rulebase']:
                    #print (item)
                    if item['type'] == 'access-section':
                        for iteminner in item['rulebase']:
                                try:
                                    dict_tmp_rule.update({
                                            'original_rule_id':iteminner['uid'],
                                            'rule_possition':iteminner['rule-number'], 
                                            'policy_name':layer_name, 
                                            'policy_section_name':item['name'],
                                            'rule_objects':get_real_uid_data(iteminner, rule['objects-dictionary'],connector),
                                            'enabled':iteminner['enabled']
                                        })
                                    
                                    all_rules_real.append(dict_tmp_rule)
                                    dict_tmp_rule ={}
                                    
                                except Exception as e:
                                    DoLogging().do_logging("\n handle_rules() - exception occured in access section: {}".format(e))
                                    
                    elif item['type'] == 'access-rule':
                        
                        try:
                            dict_tmp_rule.update({
                                'original_rule_id':item['uid'],
                                'rule_possition':item['rule-number'], 
                                'policy_name':layer_name, 
                                'rule_objects':get_real_uid_data(item, rule['objects-dictionary'], connector),
                                'policy_section_name':"Null",
                                'enabled':item['enabled']
                            })
                            
                            all_rules_real.append(dict_tmp_rule)
                            dict_tmp_rule ={} 
                            
                        except Exception as e:
                            DoLogging().do_logging("\n handle_rules() - exception occured: {}".format(e))
                            
                        
        
        rules_for_processing = _handle_hitcount_and_any(connector, all_rules_real)
        
        current_path=(os.path.dirname(os.path.abspath(__file__)))
        data_folder='{0}/data/rules_and_objects'.format(current_path)
        disabled='{0}/policyName__{1}__disabled_rules.txt'.format(data_folder, layer_name)
        zero='{0}/policyName__{1}__rules_with_zero_hitcount.txt'.format(data_folder, layer_name)
        any_obj='{0}/policyName__{1}__rules_with_ANY_src_or_dst_or_service.txt'.format(data_folder, layer_name)
        old='{0}/policyName__{1}__rules_with_older_hitcount_than_{2}days.txt'.format(data_folder, layer_name, connector.get_hitcount_back())

        with open(disabled, 'w') as outfile:
            print('saving disabled rules, count is:{}\n\n'.format(rules_for_processing['disabled_counter'])+'\n\n'.join('{}'.format(item)for item in rules_for_processing['disabled']), file=outfile) 
            DoLogging().do_logging('saving rules with zero hits for policy:{0}, count is: {1}'.format(layer_name,rules_for_processing['disabled_counter']))
        
        with open(zero, 'w') as outfile:
            print('saving rules with zero hits, count is:{}\n\n'.format(rules_for_processing['zero_counter'])+'\n\n'.join('{}'.format(item)for item in rules_for_processing['zero']), file=outfile) 
            DoLogging().do_logging('saving rules with zero hits for policy:{0}, count is: {1}'.format(layer_name,rules_for_processing['zero_counter']))
        
        with open(any_obj, 'w') as outfile:
            print('saving rules_with_ANY_src_or_dst_or_service, count is:{}\n\n'.format(rules_for_processing['any_counter'])+'\n\n'.join('{}'.format(item)for item in rules_for_processing['any']), file=outfile) 
            DoLogging().do_logging('saving rules_with_ANY_src_or_dst_or_service:{0}, count is: {1}'.format(layer_name,rules_for_processing['any_counter']))
        
        with open(old, 'w') as outfile:
            print('saving rules_with_older_hitcount_than:{0}days, count is:{1}\n\n'.format(connector.get_hitcount_back(),rules_for_processing['old_counter'])+'\n\n'.join('{}'.format(item)for item in rules_for_processing['old']), file=outfile) 
            DoLogging().do_logging('saving rules with zero hits for policy:{0}, count is: {1}'.format(layer_name,rules_for_processing['old_counter']))
        
        
    
    
        

def main():
    
    """
    main method where appropriate data methods are triggered
    """
    try:
        os.remove('logcp.elg')
    except:
        pass 
    
    DoLogging().do_logging("\n main() - main staring..")
    connector = ask_for_question()
    
    """    
    CMD to boxes you can define new command just by new dict item in list in format:
    
    {name_of_command:command}
    
    """
    
    mapping_list = [
        #{"doctor-log_script": "/bin/bash /var/tmp/doctor-log.sh > /var/tmp/doctorOut 2>/dev/null | echo \"check doctorOut in /var/tmp..doctor-log.sh must be present in /var/tmp, upload it..\""},
        #{"cpinfo_cmd":"cpinfo -y all"},
        #{"df_cmd":"df -lah"},
        #{"fw_ctl_multik_cmd":"fw ctl multik stat"},
        #{"top_cmd":"top -n 1 -b"},
        #{"free_cmd":"free -m -t"},
        #{"cpuinfo_cmd":"cat /proc/cpuinfo"},
        #{"psaux_cmd":"ps auxw"},
        #{"fw_ver_cmd":"fw ver -k"}, 
        #{"fw_stat_cmd":"fw stat"},
        #{"cphaprob_state_cmd":"cphaprob state"},
        #{"cphaprob_list_cmd":"cphaprob list"},
        #{"netstat_cmd":"netstat -ni"},
        #{"arp_table_overflow_cmd":"echo $(dmesg | grep -i \"table overflow\")"},
        #{"arp_entries_cmd":"arp -an | wc -l"},
        #{"arp_cache_cmd":"clish -c \"show arp table cache-size\""},
        #{"fw tab connections_limit_cmd":"fw tab -t connections | grep limit"},
        #{"fw_tab_connections_cmd":"fw tab -t connections -s"},
        #{"fwx_cache_cmd":"fw tab -t fwx_cache -s && echo \"\n\" && fw tab -t fwx_cache | grep limit "},
        #{"fw tab_t_host_table-s":"fw tab -t host_table -s"},
        #{"fw_ctl_pstat_mem_allocation_fail_cmd":"fw ctl pstat"},
        #{"cphaprob_syncstat_cmd":"cphaprob syncstat"},
        #{"cphaprob_a_if__cmd":"cphaprob -a if"},
        #{"show cluster failover":"clish -c \"show cluster failover\""},
        #{"proc_interrupts_cmd":"cat /proc/interrupts"},
        #{"fw-d_ctl_affinity_cmd":"fw -d ctl affinity -corelicnum"},
        #{"fwctl_affinity_cmd":"fw ctl affinity -l"},
        #{"ips_stat_cmd":"ips stat"},
        #{"ntp_status_cmd":"ntpstat"},
        #{"core_dumps_cmd":"ls -lR /var/crash/ && ls -lR /var/log/dump/usermode/"},
        #{"last_logins_by_name":"last -30"},
        #{"cplic print_cmd":"cplic print -x | more; cpstat os -f licensing | more"},
        #{"supported_api_versions_cmd":"ls -lah $FWDIR/api/docs/data/"},
        #{"cpwd_admin_list_cmd":"echo \"restarted process (checking dates and times): $(cpwd_admin list | grep -v APP | awk -F] '{print $2}' | awk '{print $1}' | sort -u | wc -l)\n\"&& cpwd_admin list"},
        #{"uptime_cmd":"uptime"},
        #{"zombies_cmd":"echo \"list of zombies:\" && zombie_procs_list=$(echo \"$(ps aux)\" | grep defunct | grep -v grep | grep -v USER); echo \"$zombie_procs_list\n\""},
        #{"IPS_update_mgmt_cmd":"mgmt_cli -r --port 4434 true show-ips-status"},
        #{"check_OS_backup_cmd":"clish -c \"show configuration\" | grep backup"},
        #{"VPN_office_mode_IP_count":"fw tab -t om_assigned_ips -s"},
        #{"user_vpn_stats_cmd":"echo; if [[ `enabled_blades 2>/dev/null` != *'vpn'* ]]; then echo ' Not a VPN gateway!'; else echo ' REMOTE ACCESS VPN STATS - Current'; printf '%.s-' {1..70}; echo; function f { if [[ \"$TERM\" == \"xterm\" ]]; then fw tab -t $1 -s | tail -n1 | awk '{print \"\033[0;32m\"$4\"\033[0m (Peak: \"$5\")\"}'; else fw tab -t $1 -s | tail -n1 | awk '{print $4\" (Peak: \"$5\")\"}'; fi; }; function t { [ \"$TERM\" == \"xterm\" ] && tput bold; }; t; echo -n \" Assigned OfficeMode IPs    : \"; f \"om_assigned_ips\"; t; echo -n \" Capsule/Endpoint VPN Users : \"; echo `f \"userc_users\"` using Visitor Mode: `vpn show_tcpt 2>/dev/null | tail -n1 | rev | awk '{print $1}' | rev | tr -s 'Mode:' '0'`; t; echo -n \" Capsule Workspace Users    : \"; f \"mob_mail_session\"; t; echo -n \" MAB Portal Users           : \"; f \"cvpn_session\"; t; echo -n \" L2TP Users                 : \"; f \"L2TP_tunnels\"; t; echo -n \" SNX Users                  : \"; f \"sslt_om_ip_params\"; echo; echo ' LICENSES'; printf '%.s-' {1..70}; t; echo; function s { awk '{ sum += $1 } END { print sum }'; }; function u { echo Unlimited; }; l=`cplic print -p 2>/dev/null | tr ' ' '\n'`; echo -n ' SecuRemote Users           : '; if [[ \"$l\" == *'srunlimited'* ]]; then u; else echo \"$l\" | grep fw1:6.0:sr | cut -c 11- | s; fi; echo -n ' Endpoint Connect Users     : '; if [[ \"$l\" == *'spcunlimit'* ]]; then u; else echo \"$l\" | grep fw1:5.0:spc | cut -c 12- | s; fi; echo -n ' Mobile Access Users        : '; if [[ \"$l\" == *'cvpnunlimited'* ]]; then u; else echo \"$l\" | grep cvpn:6.0:cvpn | cut -c 14- | tr -d 'user' | s; fi; echo -n ' SNX Users                  : '; if [[ \"$l\" == *'nxunlimit'* ]]; then u; else echo \"$l\" | grep fw1:6.0:nx | cut -c 11- | s; fi; [ \"$TERM\" == \"xterm\" ] && tput sgr0; unset l; fi; echo"},
        #{"varLogMessagesKernelErrors_cmd":"echo \"only first log file, getting all files failing via API\" && cat /var/log/messages* | grep -v 'Starting CUL' | grep -v 'Stopping CUL' | grep -v 'xpand' | grep -v 'clish' | grep -v 'last message repeated'"},
        #{"varLogMessagesClishChanges_cmd":"cat /var/log/messages | grep -i \"clish\""},
           
    ]
    
    
    
    try:    
        folders()
        handle_unused_objects(connector)
        handle_rules(connector) 
        get_targets_data(connector,mapping_list)                   
        connector.logout()
        DoLogging().do_logging("\n main() - main end..")
        
    except KeyboardInterrupt:
        DoLogging().do_logging("\n main() - ctrl+c pressed, logout and exit..")
        connector.logout()
        sys.exit(1) 
    
    
    
if __name__ == "__main__":

    main()
