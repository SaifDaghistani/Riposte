import inotify.adapters
import concurrent.futures
from helper import read_data, serialize, save_data, send_log
import threading
import os
import subprocess
import shlex


#Connect to the server
import client

#System under attack flag event
UNDER_ATTACK = threading.Event()

#Initialization of the system
#Initialization by loading the response techniques avaiable
responseTechniquesData = read_data('data/response_techniques.json')
#Get the specifications of the system
specifications = read_data('data/specifications.json')
#Send specifications to the server after serializing it
client.sock.sendall(serialize('init', specifications))


def check_undergoing_assessment():
    #First off, check if the car status is busy to see if there are unsent log files
    if specifications['is_busy']:
        print('The car is in busy status! Checking previous logs...')
        #If still busy, then look for an un-sent log to the server. This happens when the client reboots, for example
        #Get folder names (attack names, basically)
        attackList = os.listdir('data/logs/')
        #Loop through each subdirectory (attack) and send the response log
        import glob
        for attackName in attackList:
            src = "data/logs/{}/*.json".format(attackName)
            files = glob.glob(src, recursive=False)
            # Loop through files
            for single_file in files:
                json_file = read_data(single_file)
                fileName = os.path.basename(single_file)
                techniqueName = fileName.replace('.json', '')
                #Continue after performing the response
                print('running response performed method now!')
                response_performed(attackName, techniqueName, single_file)
                break


def monitor(filePath):
    print('Monitoring process is running...')
    i = inotify.adapters.Inotify()
    i.add_watch(filePath)
    for event in i.event_gen(yield_nones=False):
        (_, type_names, path, filename) = event
        if type_names == ['IN_ATTRIB']:
            #Privilege escalation attack it detected!
            UNDER_ATTACK.set()
            #If the effectiveness flag is set, that means the system is being tested for effectiveness, 
            # no need to re-run the response technique
            if not specifications['is_busy']:
                attackDetails = 'privilege_escalation'
                threading.Thread(target=response_system(attackDetails)).start()


def response_system(attackDetails):
    #Under attack state is being processed, clear it
    UNDER_ATTACK.clear()
    if not specifications['is_collaborative']:
        #After detecting the attack -> request evaluation from the server 
        evaluationThread = threading.Thread(target=request_evaluation(attackDetails))
        evaluationThread.start()
        #Wait for the thread to finish
        evaluationThread.join()
        #Clear the response ack
        client.RESPONSE_ACK.clear()
        #Load the response system
        responseSystem = read_data('data/response_system.json')
        responseTechnique = responseSystem[attackDetails]
        techniquePath = responseTechniquesData[responseTechnique] # The path for the technique script              
        running_response_technique(attackDetails, responseTechnique, techniquePath)
    else:
        #Assign car to busy and save it locally
        specifications['is_busy'] = True
        save_data('data/specifications.json', specifications)
        #Load the response system
        responseSystem = read_data('data/response_system.json')
        responseTechnique = responseSystem[attackDetails]
        #Run the response technique applied by the response system
        print('Under {} attack! Running {}!'.format(attackDetails, responseTechnique))
        techniquePath = responseTechniquesData[responseTechnique] # The path for the technique script              
        #Generate a new thread and run the response technique script
        responseThread = threading.Thread(target=running_response_technique(attackDetails, responseTechnique, techniquePath))
        responseThread.start()
        #Wait for the thread to finish
        responseThread.join()
        response_performed(attackDetails, responseTechnique, techniquePath)


def response_performed(attackDetails, responseTechnique, techniquePath):
    #Send a message to server letting it know that the response technique is performed
    client.sock.send(serialize('ack', '{}!.!{}'.format('response performed', responseTechnique)))
    #The client waits for the server to finish the effectiveness test attack
    print('Waiting for the server to perform the effectiveness attack')
    client.FINISH_TESTING_EFFECTIVENESS.wait()
    #If both are true, that means the response technique failed to stop the attack
    print('Server done with effectiveness attack')
    if UNDER_ATTACK.is_set() : isEffective = False
    elif not UNDER_ATTACK.is_set() : isEffective = True
    #Clear flags
    UNDER_ATTACK.clear()
    client.FINISH_TESTING_EFFECTIVENESS.clear()
    #Load the saved file
    print('Loading the log file')
    logFile = read_data('data/logs/{}/{}.json'.format(attackDetails, responseTechnique))
    #Add effective status to the json file
    logFile['is_effective'] = isEffective
    #Send the log so we don't keep the server waiting for log file, in case this was the last technique to be assessed
    print('Sending the log file')
    client.sock.send(send_log('log', "{}!.!{}!.!{}!.!{}".format(specifications['software_version'], specifications['hardware_specifications'], attackDetails, responseTechnique), logFile))
    #After sending the log, delete the log file
    try:
        os.remove('data/logs/{}/{}.json'.format(attackDetails, responseTechnique))
    except:
        print("Error while deleting file: ", logFile)

    #Revert changes done when the response technique applied
    print('Running revert operation')
    subprocess.run(shlex.split("{} {}".format(techniquePath, "revert")))
    print('Revert operation successful')
    #After getting back to the original state, change busy status to false
    specifications['is_busy'] = False
    #Save changes
    save_data('data/specifications.json', specifications)
    #Inform the server that the car is no longer busy
    print('Sending busy status to server. Setting it to false (the car is ready for more work)')
    client.sock.send(serialize('ack', '{}!.!{}'.format('client busy status', 'false')))

def running_response_technique(attackDetails, responseTechnique, path):
    #A place holder for log information.
    tempDict = {}
    tempDict['cpu_utilization'] = '100'

    print("Running {} from path {}".format(responseTechnique, path))
    if specifications['is_collaborative']:
        os.makedirs(os.path.dirname('data/logs/{}/{}.json'.format(attackDetails, responseTechnique)), exist_ok=True)
        save_data('data/logs/{}/{}.json'.format(attackDetails, responseTechnique), tempDict)

    #Run response technique
    subprocess.run(shlex.split("{} {}".format(path, "apply")))


def request_evaluation(attackDetails):
    #Load the response system
    responseSystem = read_data('data/response_system.json')
    #Request for evaluation from the server
    client.sock.sendall(serialize('request_evaluation', attackDetails 
    + '!.!' + responseSystem[attackDetails]))
    #Wait for the ACK from server
    client.RESPONSE_ACK.wait()


def _main():
    monitoringPath = '/etc/shadow'
    with concurrent.futures.ThreadPoolExecutor() as executor:
        #Check if the client has undergoing assessment
        executor.submit(monitor, monitoringPath)
        #Run the monitor for watching a specific file    
        executor.submit(check_undergoing_assessment)  


if __name__ == '__main__':
    _main()