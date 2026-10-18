# vd-jev demo: run demo/record.sh from the repo root (real calls, ~0.0004 USD)

Output tmp/demo-vhs.mp4

Require vd

Set Shell "bash"
Set FontSize 30
Set Width 3000
Set Height 1120
Set Padding 32
Set TypingSpeed 90ms
Set Framerate 20
Set Theme "Dracula"
Set WaitTimeout 60s

Hide
# higher-contrast command palette: orange match on dark grey instead of red on green
Type "vd --config /dev/null --color-cmdpalette='255 white on 236' --color-match='bold 215' demo/city_requests.csv"
Enter
Wait+Screen /city_requests/
Show
Sleep 3s

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
Sleep 2.5s
Enter
Sleep 500ms
Type "Does the message report a safety hazard?"
Sleep 2.5s
Enter
Wait+Screen /noul: .* rows answered/
Sleep 5s

# pick one label: comma-separated answers
Space
Sleep 300ms
Type "jev-column"
Sleep 2.5s
Enter
Sleep 500ms
Type "Which department should handle this?"
Sleep 1.5s
Tab
Type "roads, parks, noise"
Sleep 2.5s
Enter
Wait+Screen /choice: .* rows answered/
Sleep 5s

# frequency table of the chosen labels
Type "l"
Sleep 500ms
Type "F"
Sleep 6s
Type "q"
Sleep 500ms
Type "h"
Sleep 500ms

# ordered scale: answers separated by <
Space
Sleep 300ms
Type "jev-column"
Sleep 2.5s
Enter
Sleep 500ms
Type "How urgent is this request?"
Sleep 1.5s
Tab
Type "low < medium < high"
Sleep 2.5s
Enter
Wait+Screen /score: .* rows answered/
Sleep 5s

# select the rows where the model is unsure, to read them by hand
Type "ll"
Sleep 500ms
Type "z|"
Sleep 300ms
Type "0 < message_score_conf < 0.5"
Sleep 2s
Enter
Sleep 8s

Hide
Type "gq"
