
# Rule: Correlating Tor Sources in Events 

This is a rule that detects incoming network traffic where the source IP address matches a known Tor exit node stored in an Active List.

## RuleId

7004


## Matching

 1 event 

## Conditions

(InZone(
event1.,/All Filters/Default Filters/Network/Perimeter/Inbound Traffic))
And
(InActiveList(
event1.sourceAddress,/All Active Lists/Tor/Tor Exit Nodes))

## Grouped By:

event1.sourceAddress, event1.destinationAddress, event1.deviceProduct, event1.deviceVendor, event1.destinationPort, event1.applicationProtocol, event1.deviceEventClassId

## Execute actions
### On First Event
· SendToConsole( )
· Set Severity High
· SetEventField( name, Anonymizer Traffic - Tor Exit Node Detected)
· SetEventField( categoryBehavior, /Communicate/Anonymized)

## Source 

[https://medium.com/analytics-vidhya/correlating-tor-sources-in-arcsight-siem-events-using-python-92750617227a](https://medium.com/analytics-vidhya/correlating-tor-sources-in-arcsight-siem-events-using-python-92750617227a)
