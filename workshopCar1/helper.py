#Read data from a json file
def read_data(path):
    import json
    with open(path, 'r', encoding='utf-8') as json_file:
        return json.load(json_file)

#Serialize an object and send 
def serialize(messageType, obj):
    import pickle
    msg = pickle.dumps(obj)
    msg = bytes("!:" + messageType + ":!", "utf-8") + msg + bytes("!:END:!", "utf-8")
    return msg
#Save data as a json file
def save_data(path, data):
    import json
    with open(path, 'w') as outfile:
        json.dump(data, outfile)

#Serialize to send a log file
def send_log(messageType, notes, obj):
    import pickle
    msg = pickle.dumps(obj)
    msg = bytes("!:" + messageType + ":!", "utf-8") + bytes("!:START:!" + notes + "!:FINISH:!", "utf-8") + msg + bytes("!:END:!", "utf-8")
    return msg
