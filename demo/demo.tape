# vd-jev demo: vhs demo/demo.tape (run from the repo root; real calls, ~0.0004 USD)

Output demo/demo.gif

Require vd

Set Shell "bash"
Set FontSize 15
Set Width 1500
Set Height 560
Set Padding 16
Set TypingSpeed 45ms
Set Theme "Dracula"
Set WaitTimeout 60s

Hide
Type "vd --config /dev/null demo/city_requests.csv"
Enter
Wait+Screen /city_requests/
Show
Sleep 1.5s

# go to the text column
Type "c"
Sleep 300ms
Type "^message$"
Enter
Sleep 800ms

# yes/no question: leave answers empty
Space
Sleep 300ms
Type "jev-column"
Enter
Sleep 500ms
Type "Does the message report a safety hazard?"
Sleep 600ms
Enter
Wait+Screen /noul: .* rows answered/
Sleep 2.5s

# pick one label: comma-separated answers
Space
Sleep 300ms
Type "jev-column"
Enter
Sleep 500ms
Type "Which department should handle this?"
Tab
Type "roads, parks, noise"
Sleep 600ms
Enter
Wait+Screen /choice: .* rows answered/
Sleep 2.5s

# frequency table of the chosen labels
Type "l"
Sleep 500ms
Type "F"
Sleep 3s
Type "q"
Sleep 500ms
Type "h"
Sleep 500ms

# ordered scale: answers separated by <
Space
Sleep 300ms
Type "jev-column"
Enter
Sleep 500ms
Type "How urgent is this request?"
Tab
Type "low < medium < high"
Sleep 600ms
Enter
Wait+Screen /score: .* rows answered/
Sleep 2.5s

# select the rows where the model is unsure, to read them by hand
Type "ll"
Sleep 500ms
Type "z|"
Sleep 300ms
Type "0 < message_score_conf < 0.5"
Sleep 600ms
Enter
Sleep 4s

Hide
Type "gq"
