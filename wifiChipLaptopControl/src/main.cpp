#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>

// WiFi credentials
const char* ssid = "ED_2G";
const char* password = "hcirocks";

// MQTT Broker settings
const char* mqtt_server = "192.168.0.128";
const int mqtt_port = 1883;
const char* mqtt_user = "esp_lDrago_windows";
const char* mqtt_pass = "D1r2a3g4o5";
// MQTT topic for ducky scripts
const char* ducky_topic = "LDrago_windows/ducky_script";

WiFiClient espClient;
PubSubClient client(espClient);

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

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message received on topic: ");
  Serial.println(topic);

  Serial.println("Script received:");
  String script = "";
  for (unsigned int i = 0; i < length; i++) {
    script += (char)payload[i];
  }
  Serial.println(script);

  // TODO: Forward this script to the Pico or process as needed
}

void reconnect() {
  // Loop until we're reconnected
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    // Attempt to connect
    if (client.connect("ESP8266LaptopClient", mqtt_user, mqtt_pass)) {
      Serial.println("connected");
      // Subscribe to topic
      client.subscribe(ducky_topic);
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
  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
}