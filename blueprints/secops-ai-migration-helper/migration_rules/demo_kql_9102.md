//ucid: 9102
// Source https://github.com/AllThingsComputers/Sentinel-Rules/blob/main/Event%20Logs/Rare%20or%20Never%20Seen%20Events%20EventID%20Logged.txt
// Title of Detection:  Rare or Never Seen Events EventID Logged
// Authorship & Contact: https://allthingscomputers.medium.com  https://twitter.com/allthingshandle  https://allthingscomputersblog.wordpress.com/ 
// Description of the Detection:  This requires a watchlist of every event ID from this table and one of  rare event IDs
// References (if available): 
// The Logic of the Detection or Query Begins Below This Line
let time_until = 1d;
let SentinelWatchlistOfEveryEIDEver = (_GetWatchlist('AllSeenEventIDsFromEventsLog') | project SearchKey);
let rarewatchlist = (_GetWatchlist('WatchlistOfRareEventsEventIDs') | project SearchKey);
let EveryEventIDSinceWatchlistCreation = (Event
| where TimeGenerated between (datetime(2022-07-19T20:00:00)..ago(time_until))
| summarize by EventID);
let RecentRareEventIDs = (Event
| where TimeGenerated between (ago(90d)..ago(time_until))
| summarize count() by EventID
| where count_ <= 1); // Adjust sensitivity
Event
| where TimeGenerated >= ago(1h)
| extend NewEvent = iff(EventID !in (SentinelWatchlistOfEveryEIDEver.SearchKey) 
    and EventID !in (EveryEventIDSinceWatchlistCreation.EventID), "EID is New", "EID is Not New")
| extend RareEvent = iff(EventID in (rarewatchlist.SearchKey) 
    or EventID in (RecentRareEventIDs.EventID), "EID is Rare", "EID is Not Rare")
| where NewEvent == "EID is New" or RareEvent == "EID is Rare"
| project TimeGenerated, EventID, NewEvent, RareEvent
| project-reorder NewEvent, RareEvent