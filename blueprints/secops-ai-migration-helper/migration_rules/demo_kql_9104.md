//ucid: 9104
// Source: https://github.com/AllThingsComputers/Sentinel-Rules/blob/main/Security%20Event/BloodHound%20or%20Sharphound%20Artefact%20Detected.txt
// Title of Detection: BloodHound or Sharphound Artefact Detected 
// Authorship & Contact: https://allthingscomputers.medium.com  https://twitter.com/allthingshandle  https://allthingscomputersblog.wordpress.com/ 
// Description of the Detection: 
// References (if available): 
// The Logic of the Detection or Query Begins Below This Line
SecurityEvent
| where EventID == 5145 and not(Account matches regex @"DomainControllerRegexHere")
| where RelativeTargetName contains "srvsvc" or RelativeTargetName contains "Isarpc" or RelativeTargetName contains "samr"
| summarize dcount(RelativeTargetName) by IpAddress, IpPort, Account
| where dcount_RelativeTargetName>= 3 