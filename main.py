# ============================================================
# Raspberry Pi Pico 2 W + MQ-2 숫자 야구 게임
# ============================================================
#
# 하드웨어
#   MQ-2 AO(아날로그 출력) -> Pico A1 / GP27 / ADC1
#   MQ-2 GND              -> Pico GND
#
# 기능
#   1. Wi-Fi 연결
#   2. 웹 브라우저에서 게임 실행
#   3. 게임 시작 시 약 10초간 센서 평균값 측정
#   4. 입김을 불어 0~9 숫자 입력
#   5. 3자리 숫자 야구 게임
#   6. HTML/CSS/JavaScript는 이 파일 안에 포함
#
# ============================================================

import network
import socket
import machine
import time
import random


# ============================================================
# 1. Wi-Fi 설정
# ============================================================
#
# 아래 두 값을 자신의 Wi-Fi 정보로 변경하세요.
#

WIFI_SSID = "YOUR_WIFI_NAME"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"


# ============================================================
# 2. MQ-2 설정
# ============================================================
#
# Raspberry Pi Pico
# GP27 = ADC1 = A1
#
# MQ-2 모듈의 AO(Analog Output)를 연결하세요.
#

mq2 = machine.ADC(27)


# ============================================================
# 3. 입김 감도 설정
# ============================================================
#
# 처음에는 아래 값으로 사용해 보고,
# 입김이 잘 감지되지 않으면 BLOW_THRESHOLD를 낮추고,
# 입김을 불지 않았는데 감지되면 높여주세요.
#

BLOW_THRESHOLD = 1500

# 입김 세기를 0~9로 변환하기 위한 범위입니다.
#
# 예를 들어:
#
# 변화량 1000 -> 1 정도
# 변화량 3000 -> 3 정도
# 변화량 5000 -> 5 정도
#
# 실제 MQ-2 센서에 따라 값을 조절해야 합니다.
#

BLOW_RANGE = 9000


# 한 번 입김을 측정하는 시간
BLOW_TIME = 1.5


# 게임 시작 전에 센서 기준값을 측정하는 시간
CALIBRATION_TIME = 10


# ============================================================
# 4. 게임 상태 변수
# ============================================================

baseline = 0

sensor_value = 0

secret_number = ""

current_guess = ""

message = "게임 시작 버튼을 눌러주세요."

game_started = False

game_finished = False

state = "idle"

last_digit = None


# ============================================================
# 5. 센서값 읽기
# ============================================================

def read_sensor():
    """
    MQ-2 아날로그 값을 읽습니다.

    read_u16()의 값 범위는 0~65535입니다.
    """

    global sensor_value

    sensor_value = mq2.read_u16()

    return sensor_value


# ============================================================
# 6. 센서 기준값 측정
# ============================================================

def calibrate_sensor():
    """
    게임 시작 시 약 10초 동안 센서값을 측정하고
    평균값을 기준값으로 저장합니다.

    이 시간에는 센서에 입김을 불지 않는 것이 좋습니다.
    """

    global baseline
    global state
    global message

    state = "calibrating"

    total = 0
    count = 0

    start = time.ticks_ms()

    print()
    print("--------------------------------")
    print("센서 기준값 측정 시작")
    print("약 10초 동안 입김을 불지 마세요.")
    print("--------------------------------")

    while time.ticks_diff(
        time.ticks_ms(),
        start
    ) < CALIBRATION_TIME * 1000:

        value = read_sensor()

        total += value
        count += 1

        # 100ms마다 한 번 측정
        time.sleep_ms(100)

    if count > 0:
        baseline = total // count
    else:
        baseline = read_sensor()

    print("센서 기준값:", baseline)

    state = "ready"

    message = (
        "준비 완료! "
        "첫 번째 숫자를 입력하세요."
    )


# ============================================================
# 7. 3자리 비밀 숫자 만들기
# ============================================================

def make_secret_number():
    """
    중복되지 않는 3자리 숫자를 생성합니다.

    예:
        527
        814
        306

    첫 번째 숫자는 0이 되지 않도록 합니다.
    """

    digits = list(range(10))

    random.shuffle(digits)

    # 첫 번째 숫자가 0이면
    # 다른 숫자와 위치를 바꿉니다.
    if digits[0] == 0:

        for i in range(1, 10):

            if digits[i] != 0:

                digits[0], digits[i] = (
                    digits[i],
                    digits[0]
                )

                break

    return (
        str(digits[0])
        + str(digits[1])
        + str(digits[2])
    )


# ============================================================
# 8. 숫자 야구 판정
# ============================================================

def check_baseball(guess):
    """
    입력한 숫자를 비밀 숫자와 비교합니다.

    Strike:
        숫자와 위치가 모두 맞음

    Ball:
        숫자는 있지만 위치가 다름
    """

    strikes = 0
    balls = 0

    for i in range(3):

        if guess[i] == secret_number[i]:

            strikes += 1

        elif guess[i] in secret_number:

            balls += 1

    return strikes, balls


# ============================================================
# 9. 입김을 숫자로 변환
# ============================================================

def measure_blow():
    """
    약 1.5초 동안 MQ-2 센서값을 확인합니다.

    입김을 불었을 때 기준값보다 얼마나 증가했는지를
    이용해서 0~9 숫자를 결정합니다.

    반환:
        0~9  : 숫자 감지 성공
        None : 입김이 너무 약함
    """

    global state
    global message

    state = "measuring"

    start = time.ticks_ms()

    peak = baseline

    print()
    print("입김 측정 중...")

    while time.ticks_diff(
        time.ticks_ms(),
        start
    ) < BLOW_TIME * 1000:

        value = read_sensor()

        if value > peak:
            peak = value

        time.sleep_ms(20)

    difference = peak - baseline

    print("기준값:", baseline)
    print("최대값:", peak)
    print("변화량:", difference)

    # --------------------------------------------------------
    # 입김이 충분하지 않은 경우
    # --------------------------------------------------------

    if difference < BLOW_THRESHOLD:

        state = "ready"

        message = (
            "입김이 약합니다. "
            "조금 더 세게 불어주세요."
        )

        return None

    # --------------------------------------------------------
    # 변화량을 0~9로 변환
    # --------------------------------------------------------

    if difference >= BLOW_RANGE:

        digit = 9

    else:

        digit = int(
            (difference / BLOW_RANGE) * 10
        )

        if digit > 9:
            digit = 9

    print("감지된 숫자:", digit)

    state = "ready"

    return digit


# ============================================================
# 10. 게임 시작
# ============================================================

def start_game():
    """
    새로운 게임을 시작합니다.

    1. 게임 상태 초기화
    2. 10초 센서 보정
    3. 비밀 숫자 생성
    """

    global game_started
    global game_finished
    global current_guess
    global message
    global secret_number
    global last_digit

    print()
    print("==============================")
    print("게임 시작")
    print("==============================")

    game_started = True
    game_finished = False

    current_guess = ""

    last_digit = None

    message = (
        "센서 기준값을 측정합니다..."
    )

    # 10초간 센서 보정
    calibrate_sensor()

    # 비밀 숫자 생성
    secret_number = make_secret_number()

    print("비밀 숫자:", secret_number)

    message = (
        "준비 완료! "
        "첫 번째 숫자를 불어주세요."
    )


# ============================================================
# 11. 숫자 하나 입력
# ============================================================

def input_digit():
    """
    입김을 측정해서 숫자 하나를 입력합니다.
    """

    global current_guess
    global message
    global game_finished
    global last_digit
    global state

    if not game_started:
        return

    if game_finished:
        return

    # 이미 3자리라면 입력하지 않습니다.
    if len(current_guess) >= 3:
        return

    # 입김 측정
    digit = measure_blow()

    # 입김이 충분하지 않았음
    if digit is None:
        return

    last_digit = digit

    # 숫자를 문자열에 추가
    current_guess += str(digit)

    print("현재 입력:", current_guess)

    # --------------------------------------------------------
    # 아직 3자리가 안 된 경우
    # --------------------------------------------------------

    if len(current_guess) < 3:

        remaining = 3 - len(current_guess)

        message = (
            str(digit)
            + " 입력 완료! "
            + "남은 숫자 "
            + str(remaining)
            + "개"
        )

        return

    # --------------------------------------------------------
    # 3자리 완성 -> 판정
    # --------------------------------------------------------

    strikes, balls = check_baseball(
        current_guess
    )

    print(
        "결과:",
        current_guess,
        strikes,
        "S",
        balls,
        "B"
    )

    # 정답
    if strikes == 3:

        game_finished = True

        state = "finished"

        message = (
            "🎉 정답입니다! "
            + current_guess
            + " / "
            + str(strikes)
            + "S "
            + str(balls)
            + "B"
        )

    # 오답
    else:

        message = (
            current_guess
            + " → "
            + str(strikes)
            + "S "
            + str(balls)
            + "B"
            + " / 다시 도전하세요!"
        )

        # 다음 시도를 위해 입력값 초기화
        current_guess = ""


# ============================================================
# 12. JSON 상태 만들기
# ============================================================

def make_status_json():
    """
    웹 브라우저에 게임 상태를 JSON으로 전달합니다.
    """

    safe_message = message.replace(
        '"',
        '\\"'
    )

    safe_guess = current_guess.replace(
        '"',
        '\\"'
    )

    if game_finished:

        result = message

    elif current_guess:

        result = (
            "현재 입력: "
            + current_guess
        )

    else:

        result = "아직 입력한 숫자가 없습니다."

    result = result.replace(
        '"',
        '\\"'
    )

    return (
        "{"
        '"state":"' + state + '",'
        '"message":"' + safe_message + '",'
        '"guess":"' + safe_guess + '",'
        '"sensor":' + str(sensor_value) + ","
        '"baseline":' + str(baseline) + ","
        '"result":"' + result + '",'
        '"finished":'
        + ("true" if game_finished else "false")
        + "}"
    )


# ============================================================
# 13. 웹 페이지
# ============================================================
#
# 별도의 HTML 파일이 필요 없습니다.
# HTML/CSS/JavaScript를 Python 문자열에 넣었습니다.
#

HTML = """<!DOCTYPE html>

<html lang="ko">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Pico 2 W 숫자 야구</title>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    padding: 20px;

    background: #101827;
    color: white;

    font-family:
        Arial,
        "Malgun Gothic",
        sans-serif;

    text-align: center;
}

.container {
    max-width: 500px;

    margin: auto;
}

h1 {
    color: #66ccff;
}

.card {
    background: #1d293b;

    border-radius: 18px;

    padding: 20px;

    margin-top: 20px;

    box-shadow:
        0 5px 20px
        rgba(0, 0, 0, 0.3);
}

.status {
    min-height: 60px;

    display: flex;

    align-items: center;

    justify-content: center;

    padding: 10px;

    border-radius: 10px;

    background: #27364d;

    font-size: 18px;
}

.number {
    font-size: 48px;

    font-weight: bold;

    color: #ffcc66;

    margin: 20px;
}

button {
    width: 100%;

    border: none;

    border-radius: 12px;

    padding: 16px;

    margin-top: 10px;

    font-size: 18px;

    font-weight: bold;

    color: white;

    background: #2979ff;
}

button:active {
    transform: scale(0.98);
}

.blow {
    background: #e85d75;

    font-size: 22px;

    padding: 22px;
}

button:disabled {
    background: #555f6d;

    color: #aaa;
}

.result {
    margin-top: 20px;

    padding: 15px;

    border-radius: 10px;

    background: #162235;

    font-size: 18px;
}

.sensor {
    margin-top: 15px;

    color: #77dd77;

    font-size: 14px;
}

.info {
    margin-top: 15px;

    color: #aeb9c9;

    font-size: 14px;

    line-height: 1.7;
}

</style>

</head>


<body>

<div class="container">

<h1>🎯 입김 숫자 야구</h1>

<div class="card">

<div id="status" class="status">
게임 시작 버튼을 눌러주세요.
</div>

<div id="number" class="number">
-
</div>

<button id="startButton"
        onclick="startGame()">
🎮 게임 시작
</button>

<button id="blowButton"
        class="blow"
        onclick="blow()"
        disabled>
💨 입김 불기
</button>

<div id="result" class="result">
아직 결과가 없습니다.
</div>

<div class="sensor">
센서값:
<span id="sensor">-</span>
<br>
기준값:
<span id="baseline">-</span>
</div>

<div class="info">
게임 시작 후 약 10초 동안<br>
센서의 평상시 값을 측정합니다.<br><br>

그 후 입김을 불어 숫자를 입력하세요.<br>
숫자 3개가 모이면 S/B 결과가 표시됩니다.
</div>

</div>

</div>


<script>


// ==========================================================
// 서버 상태 가져오기
// ==========================================================

async function updateStatus() {

    try {

        const response =
            await fetch("/status");

        const data =
            await response.json();


        document.getElementById(
            "status"
        ).innerText = data.message;


        document.getElementById(
            "number"
        ).innerText =
            data.guess || "-";


        document.getElementById(
            "sensor"
        ).innerText =
            data.sensor;


        document.getElementById(
            "baseline"
        ).innerText =
            data.baseline;


        document.getElementById(
            "result"
        ).innerText =
            data.result;


        const blowButton =
            document.getElementById(
                "blowButton"
            );


        // 센서 보정이 끝나고
        // 입력 준비 상태일 때만 입김 버튼 활성화
        if (
            data.state === "ready"
            && !data.finished
        ) {

            blowButton.disabled = false;

        } else {

            blowButton.disabled = true;

        }

    } catch (error) {

        console.log(error);

    }

}


// ==========================================================
// 게임 시작
// ==========================================================

async function startGame() {

    const startButton =
        document.getElementById(
            "startButton"
        );

    const blowButton =
        document.getElementById(
            "blowButton"
        );


    startButton.disabled = true;

    blowButton.disabled = true;


    document.getElementById(
        "status"
    ).innerText =
        "센서 기준값을 측정하고 있습니다...";


    try {

        await fetch("/start");

    } catch (error) {

        console.log(error);

    }


    startButton.disabled = false;

    updateStatus();

}


// ==========================================================
// 입김 입력
// ==========================================================

async function blow() {

    const blowButton =
        document.getElementById(
            "blowButton"
        );


    blowButton.disabled = true;


    document.getElementById(
        "status"
    ).innerText =
        "💨 입김을 측정하고 있습니다...";


    try {

        await fetch("/blow");

    } catch (error) {

        console.log(error);

    }


    updateStatus();

}


// ==========================================================
// 0.5초마다 Pico의 상태 확인
// ==========================================================

setInterval(
    updateStatus,
    500
);


updateStatus();


</script>

</body>

</html>
"""


# ============================================================
# 14. HTTP 응답 보내기
# ============================================================

def send_response(
    client,
    content,
    content_type
):

    response = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: "
        + content_type
        + "\r\n"
        "Connection: close\r\n"
        "\r\n"
        + content
    )

    client.send(
        response.encode("utf-8")
    )


# ============================================================
# 15. Wi-Fi 연결
# ============================================================

def connect_wifi():

    wlan = network.WLAN(
        network.STA_IF
    )

    wlan.active(True)

    print()
    print("Wi-Fi 연결 중...")

    wlan.connect(
        WIFI_SSID,
        WIFI_PASSWORD
    )

    timeout = 20

    start = time.time()

    while not wlan.isconnected():

        if time.time() - start > timeout:

            print()
            print("Wi-Fi 연결 실패")

            return None

        print(".", end="")

        time.sleep(0.5)

    print()
    print()
    print("Wi-Fi 연결 성공!")

    ip = wlan.ifconfig()[0]

    print("IP 주소:", ip)

    return ip


# ============================================================
# 16. 웹 서버 만들기
# ============================================================

def create_server():

    address = socket.getaddrinfo(
        "0.0.0.0",
        80
    )[0][-1]

    server = socket.socket()

    server.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    server.bind(address)

    server.listen(1)

    # 너무 오래 기다리지 않도록 설정
    server.settimeout(0.2)

    return server


# ============================================================
# 17. 웹 요청 처리
# ============================================================

def handle_request(client):

    try:

        request = client.recv(2048)

        if not request:
            return

        request_text = request.decode(
            "utf-8",
            "ignore"
        )

        first_line = request_text.split(
            "\r\n"
        )[0]

        print("요청:", first_line)


        # ----------------------------------------------------
        # 메인 페이지
        # ----------------------------------------------------

        if first_line.startswith(
            "GET / "
        ):

            send_response(
                client,
                HTML,
                "text/html; charset=utf-8"
            )


        # ----------------------------------------------------
        # 게임 시작
        # ----------------------------------------------------

        elif first_line.startswith(
            "GET /start"
        ):

            start_game()

            send_response(
                client,
                '{"ok":true}',
                "application/json"
            )


        # ----------------------------------------------------
        # 입김 입력
        # ----------------------------------------------------

        elif first_line.startswith(
            "GET /blow"
        ):

            input_digit()

            send_response(
                client,
                '{"ok":true}',
                "application/json"
            )


        # ----------------------------------------------------
        # 상태 확인
        # ----------------------------------------------------

        elif first_line.startswith(
            "GET /status"
        ):

            send_response(
                client,
                make_status_json(),
                "application/json"
            )


        # ----------------------------------------------------
        # 없는 주소
        # ----------------------------------------------------

        else:

            response = (
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Type: text/plain\r\n"
                "Connection: close\r\n"
                "\r\n"
                "404 Not Found"
            )

            client.send(
                response.encode("utf-8")
            )

    except Exception as e:

        print(
            "요청 처리 오류:",
            e
        )

    finally:

        client.close()


# ============================================================
# 18. 프로그램 시작
# ============================================================

print()
print("========================================")
print(" Raspberry Pi Pico 2 W")
print(" MQ-2 입김 숫자 야구 게임")
print("========================================")


# Wi-Fi 연결
ip_address = connect_wifi()


# Wi-Fi 연결에 성공한 경우
if ip_address is not None:

    server = create_server()

    print()
    print("----------------------------------------")
    print("웹 서버 시작!")
    print()
    print("스마트폰이나 PC의 브라우저에서:")
    print()
    print("http://" + ip_address)
    print()
    print("으로 접속하세요.")
    print("----------------------------------------")
    print()


    # --------------------------------------------------------
    # 웹 서버 무한 반복
    # --------------------------------------------------------

    while True:

        try:

            try:

                client, address = (
                    server.accept()
                )

                print(
                    "접속:",
                    address
                )

                handle_request(
                    client
                )

            except OSError:

                # server.settimeout() 때문에
                # 일정 시간 동안 접속이 없으면 발생합니다.
                # 정상적인 상황이므로 무시합니다.
                pass

        except KeyboardInterrupt:

            print(
                "서버를 종료합니다."
            )

            server.close()

            break

        except Exception as e:

            print(
                "서버 오류:",
                e
            )

            time.sleep(1)

else:

    print()
    print("Wi-Fi 설정을 확인하세요.")
