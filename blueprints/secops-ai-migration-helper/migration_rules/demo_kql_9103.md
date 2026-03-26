//ucid: 9103
// Source https://github.com/AllThingsComputers/Sentinel-Rules/blob/main/Event%20Logs/New%20Run%20or%20RunOnce%20Scheduled%20Task.txt
// Title of Detection:   New Run/RunOnce Scheduled Task
// Authorship & Contact: https://allthingscomputers.medium.com  https://twitter.com/allthingshandle  https://allthingscomputersblog.wordpress.com/ 
// Description of the Detection:  Shell-Core EventID 9706/9707/9708 
// References (if available):  https://blog.menasec.net/2019/02/threat-hunting-20-runrunonce-EventID.html 
// The Logic of the Detection or Query Begins Below This Line
// Source https://github.com/AllThingsComputers/Sentinel-Rules/blob/main/Event%20Logs/New%20Run%20or%20RunOnce%20Scheduled%20Task.txt
Event
| where EventID in (12, 13)
| where ParameterXml matches regex @"(?i)HK(LM|CU)\\.*(\\Run\\|\\RunOnce\\).*?<"
| extend RunRunonce = trim_end('<', extract(@"(?i)(HK(LM|CU)\\.*(\\Run\\|\\RunOnce\\).*?)<", 1, ParameterXml))
| where not(RunRunonce matches regex @"(?i)\{[\w-]{36}\}exclusions")