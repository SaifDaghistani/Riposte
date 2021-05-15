import socket
import threading
import sys
from helper import serialize, save_data, read_data
import pickle

#Variables
BUFFER_SIZE = 4 * 1024
RESPONSE_ACK = threading.Event()
FINISH_TESTING_EFFECTIVENESS = threading.Event()


#Wait for incoming data from server
def receive(socket, signal):
    while signal:
        try:
            data = socket.recv(BUFFER_SIZE)
            if data != b'':
                filter_data(data)
        except:
            print("You have been disconnected from the server")
            signal = False
            break


def filter_data(data):
    #Analyze the data, it might have multiple messages stacked together
    data = data.split(b'!:END:!')
    #Loop through the messages, skipping last element that returns an empty byte string
    for message in data[:-1]:
        #If a message is received
        if b'!:message:!' in message:
            print('string message received!')
            filteredData = message.replace(b'!:message:!',b'')
            message = pickle.loads(filteredData)
            print('From server: ' + message)
        #If a file is received
        elif b'!:file:!' in message:
            filteredData = message.replace(b'!:file:!',b'')
            print('File received!')
        #file_received(self, filteredData)
        elif b'!:update:!' in message:
            filteredData = message.replace(b'!:update:!',b'')
            message = pickle.loads(filteredData).split()
            apply_update(message[0], message[1])
            sock.send(serialize('ack', 'update ok'))
            RESPONSE_ACK.set()
        elif b'!:ack:!' in message:
            filteredData = message.replace(b'!:ack:!',b'')
            message = pickle.loads(filteredData)
            if message == "best response technique is applied":
                print('ACK message received from server, running the best response technique.')
                RESPONSE_ACK.set()
            elif message == "finish testing effectiveness": FINISH_TESTING_EFFECTIVENESS.set()
        else:
            print(data)


def apply_update(attackDetails, responseTechnique):
    print('Update received! Applying: {} for: {}'.format(responseTechnique, attackDetails))
    #Read and update the response_system file
    responseSystem = read_data('data/response_system.json')
    responseSystem[attackDetails] = responseTechnique
    save_data('data/response_system.json', responseSystem)


#Get host and port
host = input("Host: ")
port = int(input("Port: "))
#host = '127.0.0.1'
#port = 12321
#Attempt connection to server
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
except:
    print("Could not make a connection to the server")
    input("Press enter to quit")
    sys.exit(0)

#Create new thread to wait for data
receiveThread = threading.Thread(target = receive, args = (sock, True))
receiveThread.start()