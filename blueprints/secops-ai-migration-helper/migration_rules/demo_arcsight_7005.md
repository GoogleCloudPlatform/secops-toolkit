# Rule: Discover Malicious Domain Lookup

This is a correlation rule that monitors DNS logs (e.g., ISC BIND) to detect when a domain query matches a known malware or suspicious domain currently monitored in an Active List.

## RuleId

7005

## Matching

 1 event 

## Conditions

(event1.deviceVendor EQ "ISC" And event1.deviceProduct EQ "BIND")
And
(event1.deviceCustomString4 IS NOT NULL)
And
(InActiveList(
event1.deviceCustomString4,/All Active Lists/Threat Intel/Malicious Domains))

##Grouped By:

event1.sourceAddress, event1.destinationAddress, event1.deviceCustomString4, event1.deviceVendor, event1.deviceProduct, event1.destinationPort

## Execute actions
### On Every Event
· SendToConsole( )
· Set Severity Very High
· SetEventField( name, Suspicious DNS Lookup - Malicious Domain)
· AddToActiveList( /All Active Lists/Monitoring/Suspicious Traffic )

## Source 

[https://dfirjournal.wordpress.com/category/arcsight/](https://dfirjournal.wordpress.com/category/arcsight/)

