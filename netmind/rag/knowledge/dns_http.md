# DNS and HTTP

## DNS (Domain Name System)
DNS translates names such as example.com into IP addresses. A client sends a query, usually over UDP port 53, to a resolver, and gets a response with the same transaction ID. The time between query and response is the DNS lookup time; normal values are a few to a few tens of milliseconds. Slow DNS makes every new web page feel slow even if the connection itself is fast. Many queries without responses suggest the DNS server is unreachable or overloaded. Unusually many queries to random-looking names can indicate malware (DNS tunnelling or domain generation).

## HTTP and HTTPS
HTTP is the web's application protocol: a client sends a request (GET, POST) and the server returns a response with a status code (200 OK, 404 Not Found, 500 Server Error). Plain HTTP uses TCP port 80 and can be read in a capture. HTTPS (port 443) is HTTP inside TLS encryption: a capture still shows IP addresses, ports, packet sizes and timing, but not the content. Slow web pages can come from DNS delay, TCP handshake delay (network RTT), TLS setup, or a slow server; separating these is the first troubleshooting step.
