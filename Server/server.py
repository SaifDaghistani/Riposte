import socket
import threading
import os
import pickle
from helper import read_data, serialize, save_data
import concurrent.futures
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
import time
import subprocess
import shlex


#Variables
connections = []
collaborativeCars = []
workList = []
techniquesForAssessment = []
#Wait event
ASSESSMENT_FLAG = threading.Event()
total_connections = 0
BUFFER_SIZE = 4 * 1024


#Load response techniques data
responseTechniquesData = read_data('data/response_techniques_database.json')


#Client class, new instance created for each connected client
#Each instance has the socket and address that is associated with items
#Along with an assigned ID and a name chosen by the client
class Client(threading.Thread):
    def __init__(self, socket, address, id, name, signal):
        threading.Thread.__init__(self)
        self.socket = socket
        self.address = address
        self.id = id
        self.name = name
        self.signal = signal
        self.socket.send(serialize('message', 'Successfully connected.'))
    
    def __str__(self):
        return str(self.id) + " " + str(self.address)
    
    #Attempt to get data from client
    #If unable to, assume client has disconnected and remove it from server
    def run(self):
        while self.signal:
            try:
                data = self.socket.recv(BUFFER_SIZE)
            except:
                print("Client " + str(self.address) + " has disconnected")
                self.signal = False
                connections.remove(self)
                if self in collaborativeCars: collaborativeCars.remove(self)
                break
            if data != b'':
                filter_data(self, data)


def filter_data(self, data):
    #Analyze the data, it might have multiple messages stacked together
    data = data.split(b'!:END:!')
    #Loop through the messages, skipping last element that returns an empty byte string
    for message in data[:-1]:
        #If an init message is received
        if b'!:init:!' in message:
            filteredData = message.replace(b'!:init:!',b'')
            init_message_received(self, filteredData)
        #If an ACK message is received
        elif b'!:ack:!' in message:
            filteredData = message.replace(b'!:ack:!',b'')
            ack_message_received(self, filteredData)
        #If a message is received
        elif b'!:message:!' in message:
            print(message)
            filteredData = message.replace(b'!:message:!',b'')
            message_received(self, filteredData)
        #If a file is received
        elif b'!:log:!' in message:
            filteredData = message.replace(b'!:log:!',b'')
            log_received(filteredData)
        #If an evaluation request is received
        elif b'!:request_evaluation:!' in message:
            if self.specifications['is_collaborative'] == False:
                filteredData = message.replace(b'!:request_evaluation:!',b'')
                evaluation_requested(self, filteredData)
            else:
                self.socket.send(serialize('message', 'Request Evaluation is only for non-collaborative systems.'))
        else:
            print(message)


def message_received(self, data):
    print('string message received!')
    message = pickle.loads(data)
    print("ID " + str(self.id) + ": " + message)


def ack_message_received(self, data):
    print('ACK message received from: ' + self.vin)
    tempMessage = pickle.loads(data)
    message = tempMessage.split('!.!')
    note = message[0]
    print(note)
    if note == 'update ok' :
        self.UPDATE_ACK.set()
    elif note == 'client busy status' : 
        if message[1] == 'false' : self.isBusy = False
    elif note == 'response performed' :
        responseTechniquePerformed = message[1]
        for task in workList:
            if task.responseTechnique == responseTechniquePerformed:
                print('responseTechniquePerformed: {}, task.responseTechnique: {}'.format(responseTechniquePerformed, task.responseTechnique))
                task.car = self
                task.EFFECTIVENESS_ACK.set()
                return


def init_message_received(self, data):
    print('init message received!')
    self.specifications = pickle.loads(data)  
    self.softwareVersion = self.specifications["software_version"]
    self.hardwareSpecifications = self.specifications["hardware_specifications"]
    self.vin = self.specifications["vin"]
    self.isCollaborative = self.specifications["is_collaborative"]
    #The busy is to show the client is not ready to collaborate at the moment
    self.isBusy = self.specifications["is_busy"]
    #Add collaborative cars into a list if its collaborative
    if self.isCollaborative: collaborativeCars.append(self)
    print("Software version: " + self.softwareVersion)
    print("Hardwawre specifications: " + self.hardwareSpecifications)
    print("VIN: " + self.vin)
    print("Collaboration status: " + str(self.isCollaborative))
    print("Busy status: " + str(self.isBusy))


def log_received(data):
    print('A log has been received!')
    #Get contents between delimiters
    tempMessage = data.split(b'!:START:!')[-1].split(b'!:FINISH:!')[0]
    #Get the rest of file data
    tempFile = data.rsplit(b'!:FINISH:!', 1)[1]
    #Filter them out
    tempMessage = tempMessage.decode('utf-8')
    message = tempMessage.split('!.!')
    softwareVersion = message[0]
    hardwareSpecifications = message[1]
    attackDetails = message[2]
    responseTechnique = message[3]
    file = pickle.loads(tempFile)
    #Save the file
    filePath = 'data/logs/{}/{}/{}/{}.json'.format(softwareVersion, hardwareSpecifications, attackDetails, responseTechnique)
    save_data(filePath, file)
    #Update the log path in the response techniques data
    responseTechniquesData[softwareVersion][hardwareSpecifications][attackDetails][responseTechnique]['log_path'] = filePath


def evaluation_requested(self, data):
    message = pickle.loads(data).split('!.!')
    self.attackDetails = message[0]
    self.responseTechniqueApplied = message[1]
    print('Evaluation requested by ID: {} for {}. The applied response technique is: {}.'.format(str(self.id), self.attackDetails, self.responseTechniqueApplied))
    #Start observer to wait for log arrivals
    #Monitor the directory and wait for the new file to arrive from the car
    logging.basicConfig(level=logging.ERROR)
    path = "data/logs/{}/{}/{}/".format(self.softwareVersion, self.hardwareSpecifications, self.attackDetails)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    #Run observer to monitor log file changes
    observer = Observer()
    event_handler = FileEventHandler(observer)
    observer.schedule(event_handler, path, recursive=False)
    observer.start()
    #Load response techniques based on the software version, hardware specifications, and attack
    suitableTechniques = responseTechniquesData[self.softwareVersion][self.hardwareSpecifications][self.attackDetails]
    #Loop through the suitable techniques and assess un-assessed techniques
    assess_techniques(self, suitableTechniques)
    #Wait for the assessment to be done
    ASSESSMENT_FLAG.wait()
    #Clear the assessment flag
    ASSESSMENT_FLAG.clear()
    #Terminate the observer
    observer.stop()
    observer.join()
    
    #Save changes to the json file
    save_data('data/response_techniques_database.json', responseTechniquesData)

    #After assessing all un-assessed techniques, evaluate them
    evaluate_techniques(self, suitableTechniques)
    
    #After making sure that all techniques are assessed and evaluated, find the 
    # best response technique for that metric and send it as update message
    final_update(self, self.attackDetails, suitableTechniques)

 
def assess_techniques(self, responseTechniques):
    #Prepare to do assessments
    for technique in responseTechniques:
        #Check if there are any un-assessed techniques
        if not responseTechniques[technique]['is_assessed']:
            techniquesForAssessment.append(technique)
    #If there were no techniques to be assessed, start assessing
    if techniquesForAssessment:
    #Update and attack the car with the technique to be assessed concurrently
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for technique in techniquesForAssessment:
                executor.submit(update_and_attack, self, self.attackDetails, technique)
    #If all techniques were previously assessed
    else: final_update(self, self.attackDetails, responseTechniques)


def update_and_attack(onRoadCar, attackDetails, responseTechnique):
    #Check for non busy collaborative cars with the same software version and hardware specs
    print("Checking for non-busy collaborative cars")
    car = find_car(onRoadCar)
    print("Car ID: {} will start assessing: {} now!".format(car.vin, responseTechnique))
    #Event to wait for an ACK message regarding the update
    car.UPDATE_ACK = threading.Event()
    print("Sending update...")
    print("-------------------------")
    #Send update with the response technique to use
    car.socket.send(serialize('update', attackDetails + " " + responseTechnique))
    #Wait for the car to ACK
    car.UPDATE_ACK.wait()
    #Clear the ACK flag
    car.UPDATE_ACK.clear()
    print("Update applied successfully!")
    print("-------------------------")

    #Create and add the task into the work list
    task = WorkTask(car, attackDetails, responseTechnique)
    workList.append(task)
    print("Simulating {} attack on car: {} using technique: {}".format(attackDetails, car.vin, responseTechnique))
    print("*************************")

    #Start the attack simulation process
    attackData = read_data('data/attack_simulations.json')
    attackPath = attackData[attackDetails]
    #Run the attack script
    print('car address is: {}'.format(car.address[0]))
    print(type(car.address[0]))
    print('attack path is: {}'.format(attackPath))
    subprocess.run(shlex.split("{} {}".format(attackPath, car.address[0])))
    
    #After initiating the attack, measure the duration
    task.startTime = time.time()
    print("start: ", task.startTime)
    
    #Wait for effectiveness ACK from client showing that the client has performed the response technique and waiting for the effectiveness test
    task.EFFECTIVENESS_ACK.wait()
    #Mark the elapsed time
    task.elapsedTime = time.time() - task.startTime

    #Re-initiate the attack simulation again to check for effectiveness
    #Keep in mind that the car might get disconnected, so rely on the VIN instead
    #Run the attack script
    print('Re-initiating the attack to test for effectiveness...')
    subprocess.run(shlex.split("{} {}".format(attackPath, task.car.address[0])))

    #After running the attack script, send a message to let the client know that the server has finished attacking
    task.car.socket.send(serialize('ack', 'finish testing effectiveness'))
    #Wait for ACK on receiving the log file
    print("Waiting for the log file...")
    task.LOG_ACK.wait()
    #Update the technique's data
    responseTechniquesData[task.car.softwareVersion][task.car.hardwareSpecifications][attackDetails][responseTechnique]['is_assessed'] = True
    responseTechniquesData[task.car.softwareVersion][task.car.hardwareSpecifications][attackDetails][responseTechnique]['duration'] = task.elapsedTime
    #Remove task from the work list
    workList.remove(task)
    #Check if this is the last task
    if not workList:
        ASSESSMENT_FLAG.set()


#Evaluation based on logs can be performed here, e.g. based on CPU utilization, etc. 
# However, this thesis focuses on time efficiency only
def evaluate_techniques(self, responseTechniques):
    print("Evaluating techniques...")
    #If one technique is not evaluated, then start the evaluation process
    isEvaluationRequired = False
    for technique in responseTechniques:
        if not responseTechniques[technique]['is_evaluated']:
            isEvaluationRequired = True
            break
    #Otherwise, no need for evaluation
    if not isEvaluationRequired : return
    #Update response techniques database
    import glob
    src = "data/logs/{}/{}/{}/".format(self.softwareVersion, self.hardwareSpecifications, self.attackDetails)
    files = glob.glob('{}/*'.format(src), recursive=False)
    # Loop through files
    for single_file in files:
        json_file = read_data(single_file)
        fileName = os.path.basename(single_file)
        techniqueName = fileName.replace('.json', '')
        isEffective = json_file['is_effective']
        responseTechniquesData[self.softwareVersion][self.hardwareSpecifications][self.attackDetails][techniqueName]['is_effective'] = isEffective

    #Add every effective technique and its duration    
    effectiveTechniques = {}
    for technique in responseTechniques:
        if responseTechniques[technique]['is_effective']: 
            effectiveTechniques[technique] = responseTechniques[technique]['duration']
    #Get the lowest duration technique
    bestResponseTechnique = min(effectiveTechniques, key=effectiveTechniques.get)
    print("Effective techniques are: ",  effectiveTechniques)
    print("Best effective response technique is {}.".format(bestResponseTechnique))
    #Modify as necessary
    responseTechniquesData[self.softwareVersion][self.hardwareSpecifications][self.attackDetails][bestResponseTechnique]['is_most_efficient'] = True
    responseTechniquesData[self.softwareVersion][self.hardwareSpecifications][self.attackDetails][bestResponseTechnique]['is_evaluated'] = True
    for technique in responseTechniques:
        if not technique == bestResponseTechnique:
            responseTechniquesData[self.softwareVersion][self.hardwareSpecifications][self.attackDetails][technique]['is_most_efficient'] = False
            responseTechniquesData[self.softwareVersion][self.hardwareSpecifications][self.attackDetails][technique]['is_evaluated'] = True

    #Save changes to the json file
    save_data('data/response_techniques_database.json', responseTechniquesData)

    
def final_update(self, attackDetails, responseTechniques):
    bestResponseTechnique = ''
    #Loop through the techniques
    for technique in responseTechniques:
        #Find the best response technique for the metric requested
        if responseTechniques[technique]['is_most_efficient']:
            bestResponseTechnique = technique
            break
    #Print out the data for response techniques
    print(tabulate_data(responseTechniques))
    #Check if the onRoadCar is using the best response technique
    if self.responseTechniqueApplied == bestResponseTechnique:
        self.socket.send(serialize('ack', "best response technique is applied"))
        print("{} is already using the most efficient response technique. ACK sent!".format(self.vin))
    else:
        #Send the final update
        print("Sending final update!")
        print("-------------------------")
        self.UPDATE_ACK = threading.Event()
        self.socket.send(serialize('update', attackDetails + " " + bestResponseTechnique))
        #Wait for the car to ACK
        self.UPDATE_ACK.wait()
        #Clear the flag
        self.UPDATE_ACK.clear()
        print("Update applied successfully!")
        print("-------------------------")


def find_car(onRoadCar):
    import time
    import random
    while True:
        for car in collaborativeCars:
            if car.softwareVersion == onRoadCar.softwareVersion and car.hardwareSpecifications == onRoadCar.hardwareSpecifications and not car.isBusy:
                #Assign the car to: busy
                car.isBusy = True
                return car
        time.sleep(random.uniform(0, 1))


def tabulate_data(responseTechniques):
    from prettytable import PrettyTable
    table = PrettyTable()

    table.field_names = ["Response Technique Name", "Is Effective", "Duration", "Is Effective And Most Efficient"]
    for technique in responseTechniques:
        table.add_row([technique, str(responseTechniques[technique]['is_effective']), str(responseTechniques[technique]['duration']), str(responseTechniques[technique]['is_most_efficient'])])

    return table


class WorkTask():
    def __init__(self, car, attackDetails, responseTechnique):
        self.car = car
        self.vin = self.car.vin
        self.softwareVersion = self.car.softwareVersion
        self.hardwareSpecifications = self.car.hardwareSpecifications
        self.attackDetails = attackDetails
        self.responseTechnique = responseTechnique
        self.LOG_ACK = threading.Event()
        self.EFFECTIVENESS_ACK = threading.Event()


class FileEventHandler(FileSystemEventHandler):
    def __init__(self, observer):
        self.observer = observer

    def on_modified(self, event):
        if not event.is_directory:
            for task in workList:
                if event.src_path.endswith(task.responseTechnique + ".json"):
                    print ("{} log has been received!".format(task.responseTechnique))
                    task.LOG_ACK.set()
 

#Wait for new connections
def newConnections(socket):
    while True:
        sock, address = socket.accept()
        global total_connections
        connections.append(Client(sock, address, total_connections, "Name", True))
        connections[len(connections) - 1].start()
        ID = str(connections[len(connections) - 1])
        print("New connection at ID {}".format(ID))
        total_connections += 1

def main():
    #Get host and port
    host = input("Host: ")
    port = int(input("Port: "))
    #host = '127.0.0.1'
    #port = 12321

    #Create new server socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, port))
    sock.listen(5)
    #Create new thread to wait for connections
    newConnectionsThread = threading.Thread(target = newConnections, args = (sock,))
    newConnectionsThread.start()
    
main()
