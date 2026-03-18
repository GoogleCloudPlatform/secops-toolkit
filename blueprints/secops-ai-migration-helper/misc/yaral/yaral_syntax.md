# YARA-L 2.0 Functions Quick Reference

Here is a consolidated list of commonly used YARA-L 2.0 functions with examples, based on the official Google Cloud documentation. 🧑‍💻

---

## String Functions
These functions are used to manipulate and analyze string data.

| Function | Description | Example |
|---|---|---|
| **`strings.coalesce(val1, val2, ...)`** | Returns the first non-null string value from a list of arguments. | `strings.coalesce($e.principal.user.userid, $e.principal.user.email_addresses)` |
| **`strings.concat(str1, str2, ...)`** | Concatenates two or more strings together. | `strings.concat("File path: ", $e.target.file.full_path)` |
| **`strings.to_lower(str)`** | Converts a string to lowercase. | `strings.to_lower($e.principal.hostname)` |
| **`strings.to_upper(str)`** | Converts a string to uppercase. | `strings.to_upper($e.target.process.name)` |
| **`strings.contains(haystack, needle)`** | Returns `true` if the `haystack` string contains the `needle` string. | `strings.contains($e.principal.process.command_line, "powershell")` |
| **`strings.extract_domain(url)`** | Extracts the domain from a URL. | `strings.extract_domain($e.network.http.url)` |
| **`strings.split(str, delimiter)`** | Splits a string into an array of strings based on a delimiter. | `strings.split($e.principal.process.command_line, " ")` |
| **`strings.starts_with(str, prefix)`** | Returns `true` if the string starts with the specified prefix. | `strings.starts_with($e.target.file.full_path, "/tmp/")` |
| **`strings.substr(str, offset, length)`** | Returns a substring of a given string. | `strings.substr($e.principal.user.userid, 0, 5)` |
| **`strings.trim(str)`**| Removes leading and trailing whitespace from a string. | `strings.trim("  some text  ")` |

---

## Regular Expression Functions
These functions allow you to use regular expressions for more complex pattern matching.

| Function | Description | Example |
|---|---|---|
| **`re.regex(text, pattern)`** | Returns `true` if the `text` matches the regular expression `pattern`. | `re.regex($e.principal.process.command_line, `\\bsvchost(\\.exe)?\\b`)` |
| **`re.capture(text, pattern)`** | Returns the first captured group from a regular expression match. | `re.capture($e.network.http.url, `user=([^&]+)`)` |
| **`re.replace(text, pattern, replacement)`** | Replaces all occurrences of a pattern in a string with a replacement string. | `re.replace($e.target.file.full_path, `\\.log$`, ".txt")` |

---

## Math Functions
These functions perform mathematical operations.

| Function | Description | Example |
|---|---|---|
| **`math.abs(num)`** | Returns the absolute value of a number. | `math.abs(-10)` |
| **`math.ceil(num)`** | Rounds a number up to the nearest integer. | `math.ceil(3.14)` |
| **`math.floor(num)`** | Rounds a number down to the nearest integer. | `math.floor(3.14)` |
| **`math.round(num)`** | Rounds a number to the nearest integer. | `math.round(3.5)` |

---

## Array Functions
These functions are used to work with arrays of data.

| Function | Description | Example |
|---|---|---|
| **`arrays.contains(array, value)`** | Returns `true` if the array contains the specified value. | `arrays.contains($e.principal.ip, "192.168.1.100")` |
| **`arrays.length(array)`**| Returns the number of elements in an array. | `arrays.length($e.principal.user.email_addresses)` |
| **`arrays.index_to_str(array, index)`** | Returns the string element at a specific index in an array. | `arrays.index_to_str(strings.split($e.principal.process.command_line, " "), 0)`|

---

## Timestamp Functions
These functions help you work with time-based data. 🕰️

| Function | Description | Example |
|---|---|---|
| **`timestamp.now()`** | Returns the current Unix timestamp in seconds. | `timestamp.now()` |
| **`timestamp.get_hour(unix_seconds)`** | Returns the hour (0-23) from a Unix timestamp. | `timestamp.get_hour($e.metadata.event_timestamp.seconds)` |
| **`timestamp.diff(t1, t2)`** | Returns the difference in seconds between two Unix timestamps. | `timestamp.diff($e2.metadata.event_timestamp.seconds, $e1.metadata.event_timestamp.seconds)` |