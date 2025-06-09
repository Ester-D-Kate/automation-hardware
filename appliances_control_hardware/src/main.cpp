#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

const char* ssid = "Airtel_arun_7500";
const char* password = "7087523885s";

const char* mqtt_server = "192.168.1.4";
const int mqtt_port = 1883;
const char* mqtt_user = "appliances";
const char* mqtt_pass = "A1p2l3i4a5n6c7e";
const char* control_topic = "appliances/room_switchboard/control";
const char* state_topic   = "appliances/room_switchboard/state"; 

struct PinMap {
  const char* name;
  uint8_t pin;
} pinMap[] = {
  {"d0", D0},
  {"d1", D1},
  {"d2", D2},
  {"d3", D3},
  {"d4", D4},
  {"d5", D5},
  {"d6", D6},
  {"d7", D7},
  {"d8", D8}
};
const int pinCount = sizeof(pinMap) / sizeof(pinMap[0]);

WiFiClient espClient;
PubSubClient client(espClient);

void setupPins() {
  for (int i = 0; i < pinCount; i++) {
    pinMode(pinMap[i].pin, OUTPUT);
    digitalWrite(pinMap[i].pin, LOW); 
  }
}

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected, IP address: ");
  Serial.println(WiFi.localIP());
}

void publish_state() {
  StaticJsonDocument<256> doc;
  for (int i = 0; i < pinCount; i++) {
    doc[pinMap[i].name] = digitalRead(pinMap[i].pin) == HIGH ? "on" : "off";
  }
  char payload[256];
  serializeJson(doc, payload, sizeof(payload));
  client.publish(state_topic, payload, true); 
  Serial.print("Published state: ");
  Serial.println(payload);
}

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("]: ");
  payload[length] = '\0'; 
  Serial.println((char*)payload);

  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, payload);

  if (error) {
    Serial.print("deserializeJson() failed: ");
    Serial.println(error.c_str());
    return;
  }

  for (JsonPair kv : doc.as<JsonObject>()) {
    const char* pinLabel = kv.key().c_str();
    const char* value = kv.value().as<const char*>();

    for (int i = 0; i < pinCount; i++) {
      if (strcasecmp(pinMap[i].name, pinLabel) == 0) {
        if (strcasecmp(value, "on") == 0) {
          digitalWrite(pinMap[i].pin, HIGH);
          Serial.printf("Set %s HIGH\n", pinLabel);
        } else {
          digitalWrite(pinMap[i].pin, LOW);
          Serial.printf("Set %s LOW\n", pinLabel);
        }
      }
    }
  }
  publish_state();
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (client.connect("ESP8266ApplianceClient", mqtt_user, mqtt_pass)) {
      Serial.println("connected");
      client.subscribe(control_topic);
      publish_state(); 
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(". Try again in 5 seconds");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  setupPins();
  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
  publish_state(); 
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
}