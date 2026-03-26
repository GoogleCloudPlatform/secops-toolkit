// ucid: 9105
// Source: https://github.com/AllThingsComputers/Sentinel-Rules/blob/main/Security%20Event/Failed%20Logon%20Attempt%20with%20Null%20Network%20address.txt
// Title of Detection:    Failed Logon Attempt with Null Network address 
// Authorship & Contact: https://allthingscomputers.medium.com  https://twitter.com/allthingshandle  https://allthingscomputersblog.wordpress.com/ 
// Description of the Detection:   Event ID 4625 with logon type (3, 10) and source Network address is null or "-" and account name not has the value $. 
// References (if available): https://www.socinvestigation.com/threat-hunting-with-windows-event-ids-4625-4624/ 
// The Logic of the Detection or Query Begins Below This Line
SecurityEvent
| where EventID == 4625 and LogonType in (3, 10) and (isempty(IpAddress) or IpAddress == "-") and TargetAccount !endswith "$