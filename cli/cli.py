import ipaddress
import requests
from enum import Enum
import json

class Options(Enum):
    # IP address
    WELCOME_GET_IP = 1,
    GET_IP = 2,
    INVALID_IP = 3,
    # Authentication
    GET_AUTH = 4,
    INVALID_AUTH = 5,
    # API
    API_OPTIONS = 6,
    SELECT_CONVERSATION = 7,


    CONVERSATION_OPTIONS = 8,



def handle_ip_address(user_response):
    def is_valid_ipv4(ip):
        try:
            ipaddress.IPv4Address(ip)
            return True
        except ValueError:
            return False
        
    ip = None
    if user_response == "":
        ip = "localhost"
        option = Options.GET_AUTH
    elif is_valid_ipv4(user_response):
        ip = user_response
        option = Options.GET_AUTH
    else:
        option = Options.INVALID_IP
    return option, ip

def handle_auth_token(user_response, ip):
    auth_token = None
    option = None
    headers = {
        "Authorization": f"Bearer {user_response}"
    }
    # try sending request
    try:
        response = requests.get(f"http://{ip}:4000/api/conv", headers=headers)
        if response.status_code == 401:
            option = Options.INVALID_AUTH
            auth_token = None
        else:
            try:
                response.raise_for_status()
                option = Options.API_OPTIONS
                auth_token = user_response
            except requests.exceptions.HTTPError as e:
                print("HTTP error:", e)
                print("Response body:", response.text)
                option = Options.GET_IP
                auth_token = None
    except Exception as e:
        print("Error: Could not connect to IP specified address")
        option = Options.GET_IP
        auth_token = None
    return option, auth_token

def main():
    option = Options.WELCOME_GET_IP
    ip = None
    auth_token = None
    conv_id = None
    while True:
        match(option):
            case Options.WELCOME_GET_IP:
                user_response = input("\nWelcome to the ODIN command line tool. Please specify the IP address of the host (press enter for local host):\n"
                    + "> ").strip()
                option, ip = handle_ip_address(user_response)
            case Options.GET_IP:
                user_response = input("\nPlease specify the IP address of the host (press enter for local host):\n"
                    + "> ").strip()
                option, ip = handle_ip_address(user_response)
            case Options.INVALID_IP:
                user_response = input("\nInvalid IP. Please enter valid IPv4 address (or press enter for local host):\n"
                    + "> ").strip()
                option, ip = handle_ip_address(user_response)
            case Options.GET_AUTH:
                assert ip is not None
                user_response = input("\nEnter mem/lm_studio API key:\n"
                    + "> ").strip()
                option, auth_token = handle_auth_token(user_response, ip)
            case Options.INVALID_AUTH:
                assert ip is not None
                user_response = input("\nInvalid API_key. Enter mem/lm_studio API key:\n"
                    + "> ").strip()
                option, auth_token = handle_auth_token(user_response, ip)
            case Options.API_OPTIONS:
                assert ip is not None
                assert auth_token is not None
                user_response = input("\nPlease select action:\n\n"
                    + "\t1. Select conversation by conv_id\n"
                    + "\t2. Create conversation\n"
                    + "\t3. List all conversations (conv_list)\n"
                    + "\t4. List LLM requests (llm_request_list)\n"
                    + "> ").strip()
                
                print("\n")                
                headers = {
                    "Authorization": f"Bearer {auth_token}"
                }

                match(user_response):
                    case "1":
                        option = Options.SELECT_CONVERSATION
                    case "2":
                        response = requests.post(f"http://{ip}:4000/api/conv", headers=headers)
                        try:
                            response.raise_for_status()
                            conv_id = response.json()[0]["id"]
                            # print(json.dumps(response.json(), indent=2))
                            option = Options.CONVERSATION_OPTIONS
                        except requests.exceptions.HTTPError as e:
                            print("HTTP error:", e)
                            print("Response body:", response.text)
                    case "3":
                        response = requests.get(f"http://{ip}:4000/api/conv", headers=headers)
                        try:
                            response.raise_for_status()
                            print(json.dumps(response.json(), indent=2))
                            option = Options.API_OPTIONS
                        except requests.exceptions.HTTPError as e:
                            print("HTTP error:", e)
                            print("Response body:", response.text)
                    case "4":
                        response = requests.get(f"http://{ip}:4000/api/llm_request", headers=headers)
                        try:
                            response.raise_for_status()
                            print(json.dumps(response.json(), indent=2))
                            option = Options.API_OPTIONS
                        except requests.exceptions.HTTPError as e:
                            print("HTTP error:", e)
                            print("Response body:", response.text)
                    case _:
                        print("\nError - Invalid user input")
            case Options.SELECT_CONVERSATION:
                assert ip is not None
                assert auth_token is not None
                user_response = input("\nPlease enter conversation ID (leave empty to return to previous page):\n"
                                      + "> ").strip()
                
                if user_response == "":
                    option = Options.API_OPTIONS
                    continue

                headers = {
                    "Authorization": f"Bearer {auth_token}"
                }
                response = requests.get(f"http://{ip}:4000/api/conv/{user_response}", headers=headers)
                try:
                    response.raise_for_status()
                    conv_id = user_response
                    print(json.dumps(response.json(), indent=2))
                    option = Options.CONVERSATION_OPTIONS
                except requests.exceptions.HTTPError as e:
                    print("HTTP error:", e)
                    print("Response body:", response.text)
            case Options.CONVERSATION_OPTIONS:
                assert ip is not None
                assert auth_token is not None
                assert conv_id is not None
                user_response = input(f"\nConversation id: {conv_id}\n\nPlease select action:\n\n"
                    + "\t1. Post new message\n"
                    + "\t2. Retrieve conversation\n"
                    + "\t3. Delete conversation\n"
                    + "\t4. Main menu\n"
                    + "> ").strip()
                
                print("\n")                
                headers = {
                    "Authorization": f"Bearer {auth_token}"
                }

                match(user_response):
                    case "1":
                        user_response = input("\nPlease enter message:\n"
                                      + "> ").strip()
                        message = user_response
                        data = {"content": [{"type": "text", "text": message}]}
                        
                        headers = {
                            "Authorization": f"Bearer {auth_token}",
                            "Content-Type": "application/json"
                        }
                        response = requests.post(f"http://{ip}:4000/api/conv/{conv_id}", headers=headers, data=json.dumps(data))
                        try:
                            response.raise_for_status()
                            print(json.dumps(response.json(), indent=2))
                        except requests.exceptions.HTTPError as e:
                            print("HTTP error:", e)
                            print("Response body:", response.text)
                    case "2":
                        headers = {
                            "Authorization": f"Bearer {auth_token}"
                        }
                        response = requests.get(f"http://{ip}:4000/api/conv/{conv_id}", headers=headers)
                        try:
                            response.raise_for_status()
                            print("Conversation successfully deleted.")
                            # print(json.dumps(response.json(), indent=2))
                            conv_id = None
                            option = Options.API_OPTIONS
                        except requests.exceptions.HTTPError as e:
                            print("HTTP error:", e)
                            print("Response body:", response.text)
                    case "3":
                        headers = {
                            "Authorization": f"Bearer {auth_token}"
                        }
                        response = requests.delete(f"http://{ip}:4000/api/conv/{conv_id}", headers=headers)
                        try:
                            response.raise_for_status()
                            print("Conversation successfully deleted.")
                            print(json.dumps(response.json(), indent=2))
                        except requests.exceptions.HTTPError as e:
                            print("HTTP error:", e)
                            print("Response body:", response.text)
                    case "4":
                        conv_id = None
                        option = Options.API_OPTIONS
                    case _:
                        print("\nError - Invalid user input")
if __name__ == "__main__":
    main()