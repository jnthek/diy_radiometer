#include <OneWire.h>
#include <DallasTemperature.h>

#define ONE_WIRE_BUS 10 //Pin where DQ of DS18B20 is connected, requires 4.7k pullup to 5V
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

int ac = 4; //Antenna or internal load control line
int ns = 3; //Noise source or load control line
char ctrl_b;
float temperature;
void setup() 
{
  Serial.begin(115200);
  pinMode(ac, OUTPUT);
  pinMode(ns, OUTPUT);
  digitalWrite(ac, LOW); 
  digitalWrite(ns, LOW);
  sensors.begin(); // 
}

void loop() 
{  
  if (Serial.available() > 0) 
  {
    ctrl_b = (char) Serial.read();
    sensors.requestTemperatures(); 
    temperature = sensors.getTempCByIndex(0);
    if (ctrl_b == 65) //A
    {
      digitalWrite(ac, LOW);
      digitalWrite(ns, LOW);
      Serial.print(temperature);
      Serial.print("\n");
    }
    else if (ctrl_b == 67) //C
    {
      digitalWrite(ac, HIGH);
      digitalWrite(ns, LOW);
      Serial.print(temperature);
      Serial.print("\n");
    }
    else if (ctrl_b == 72) //H
    {
      digitalWrite(ac, HIGH);
      digitalWrite(ns, HIGH);
      Serial.print(temperature);
      Serial.print("\n");
    }
  }           
}

