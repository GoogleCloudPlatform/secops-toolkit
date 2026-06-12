# PASS THE TICKET - QRADAR
## Source
https://github.com/System-CTL/QRadar-AQL-Queries/blob/master/Kerberos%20Use-Cases/Pass%20the%20Ticket.md 

## Analytics

SUBSET RULE: Every time you see a TGT issued (Event ID 4768), you record the username in a Reference Set(TTL 10 hours).    
FINAL USE-CASE LOGIC: when you see a TGS request (4769) or TGT renewal (4770), QRadar checks that “Reference Set” to see if that username was seen recently.

If it was seen → normal behavior (user requested TGT before).
If it was NOT seen → suspicious (the TGT might have been stolen and used on a different machine).

FALSE POSITIVE: DELEGATED TGS requests, DC Machines

## SUBSET RULE
*enable this and triggered events should be populated in reference_set*
```
and when the event(s) were detected by one or more of Microsoft Windows Security Event Log
and when the event matches Event ID is any of 4768
```

## FINAL USE-CASE LOGIC
```
and when the event(s) were detected by one or more of Microsoft Windows Security Event Log
and when the event matches Event ID is any of [4769 or 4770]
and NOT when any of User-Name (custom) are contained in any of [reference_set]
and NOT when the event matches Source IP is any of [DC_SOURCE_IPs]
```