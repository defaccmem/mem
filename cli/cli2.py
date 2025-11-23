import requests
import readline
import json

class Client:
    def __init__(self):
        self.local = True
        self.apikey = {"local": "", "cloud": ""}
        self.current_conv = ""
        self._read_configuration()

    @property
    def base_url(self) -> str:
        return "http://localhost:4000" if self.local else "https://api.snow-white.org"
    
    @property
    def headers(self):
        apikey = self.apikey["local"] if self.local else self.apikey["cloud"]
        return {"Authorization": f"Bearer {apikey}", "Content-Type": "application/json"}

    def print_menu(self):
        print("/server [local/cloud] [apikey]")
        print("/conv")
        print("/conv new")
        print("/conv del [convid]")
        print("/conv [convid]")
        print("/ls")
        print("or just type stuff to add it to the conversation.")
        print()
        print(f"Server: {'local' if self.local else 'cloud'}, Current conversation: {self.current_conv}")
    
    def _write_configuration(self):
        with open(".client_config", "w") as f:
            json.dump({"local": self.local, "apikey": self.apikey, "current_conv": self.current_conv}, f)

    def _read_configuration(self):
        try:
            with open(".client_config", "r") as f:
                config = json.load(f)
                self.local = config.get("local", True)
                self.apikey = config.get("apikey", {"local": "", "cloud": ""})
                self.current_conv = config.get("current_conv", "")
        except FileNotFoundError:
            pass

    def reconfigure(self, local: bool, apikey: str | None):
        self.local = local
        if apikey is not None:
            self.apikey["local" if local else "cloud"] = apikey
        self.current_conv = ""
        self._write_configuration()

    def ls_conv(self):
        response = requests.get(f"{self.base_url}/api/conv", headers=self.headers)
        print("Available conversations:")
        if response.status_code == 200:
            conversations = response.json()["conversations"]
            for conv in conversations:
                star = "* " if conv["id"] == self.current_conv else "  "
                print(f"{star}ID: {conv['id']}, Topic: {conv['topic']}")
        else:
            print("Failed to fetch conversations.")

    def switch_to_new_conv(self):
        response = requests.post(f"{self.base_url}/api/conv", headers=self.headers, json={})
        response.raise_for_status()
        if response.status_code == 200:
            conv = response.json()
            self.current_conv = conv["id"]
            print(f"Switched to new conversation with ID: {self.current_conv}")
        else:
            print("Failed to create a new conversation.")

    def _print_conv(self, conv_data: dict):
        print(f"Conversation ID: {conv_data['id']}")
        print(f"Topic: {conv_data['topic']}")
        print("Messages:")
        for msg in conv_data["messages"]:
            role = "User" if msg["role"] == "user" else "AI"
            for content in msg["content"]:
                assert content["type"] == "text"
                print(f"{role}: {content['text']}")
                req_ids = msg.get("llm_request_ids", [])
                if len(req_ids) > 0:
                    print(f"  (LLM Request IDs: {', '.join(req_ids)})")
            print("---")

    def print_current_conv(self):
        if not self.current_conv:
            print("No active conversation. Use /conv [convid/new] to start or switch to a conversation.")
            return
        response = requests.get(f"{self.base_url}/api/conv/{self.current_conv}", headers=self.headers)
        if response.status_code == 200:
            conv_data = response.json()
            self._print_conv(conv_data)
        else:
            print("Failed to fetch conversation.")

    def say(self, message: str):
        if not self.current_conv:
            print("No active conversation. Use /conv [convid/new] to start or switch to a conversation.")
            return
        payload = {
            "content": [{"type": "text", "text": message}]
        }
        response = requests.post(f"{self.base_url}/api/conv/{self.current_conv}", headers=self.headers, json=payload)
        if response.status_code == 200:
            reply = response.json()
            self._print_conv(reply)
        else:
            print("Failed to send message.")

    def delete_conversation(self, conv_id: str):
        response = requests.delete(f"{self.base_url}/api/conv/{conv_id}", headers=self.headers)
        if response.status_code == 200:
            print(f"Conversation {conv_id} deleted.")
            if self.current_conv == conv_id:
                self.current_conv = ""
        else:
            print("Failed to delete conversation.")


if __name__ == "__main__":
    client = Client()
    try:
        readline.read_history_file(".history")
    except FileNotFoundError:
        pass
    client.print_menu()

    while True:
        inp = input(">> ").strip()
        readline.write_history_file(".history")
        words = inp.split()
        if len(words) == 0:
            continue
        match words[0]:
            case "/server":
                if len(words) not in [2,3] or words[1] not in ["local", "cloud"]:
                    print("Usage: /server [local/cloud] [apikey]")
                    continue

                client.reconfigure(words[1] == "local", words[2] if len(words) == 3 else None)
                print("Configuration updated.")
                client.ls_conv()
            case "/conv":
                if len(words) == 1:
                    client.ls_conv()
                    continue

                if len(words) == 3 and words[1] == "del":
                    conv_id = words[2]
                    client.delete_conversation(conv_id)
                    continue

                if len(words) != 2:
                    print("Usage: /conv [convid/new]")
                    continue
                if words[1] == "new":
                    client.switch_to_new_conv()
                else:
                    client.current_conv = words[1]
                    print(f"Switched to conversation with ID: {client.current_conv}")
            case "/ls":
                client.print_current_conv()
            case _:
                if words[0].startswith("/"):
                    print("Unknown command.")
                    client.print_menu()
                    continue
                client.say(inp)