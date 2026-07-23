import http.client
import json
import ssl


def reply():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    body = json.dumps({
        "chatId": "210574529011868@lid",
        #"quotedMessageId": "false_210574529011868@lid_2A050D4B1D7F336335C2",
        "text": "ok"
    })

    conn = http.client.HTTPSConnection("restcos.online", context=ctx)
    conn.request(
        "POST",
        "/api/sessions/c750c6de-ac23-4036-a213-9ab14042b81d/messages/send-text",
        body=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": "Kz8nR7D1qL9sX0pF2vB5gY6jC3mN4aT7hP9uS2dG5kZ8bQ1wE3rV6tJ0fM7cX9lD2sB5n"
        }
    )
    res = conn.getresponse()
    print(json.loads(res.read().decode("utf-8")))


if __name__ == "__main__":
    reply()