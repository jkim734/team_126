"""인증키를 파일에 저장하지 않고 로컬 웹 서버를 실행한다."""

from __future__ import annotations

import getpass
import os


def main() -> None:
    print("공공데이터 인증키를 붙여넣고 Enter를 누르세요.")
    print("입력 내용은 화면에 표시되거나 파일에 저장되지 않습니다.")
    api_key = getpass.getpass("DATA_GO_KR_API_KEY: ").strip()
    if not api_key:
        raise SystemExit("인증키가 입력되지 않아 서버를 시작하지 않습니다.")

    # 인증키를 사용하는 웹 서버와 같은 Python 프로세스에 직접 설정한다.
    os.environ["DATA_GO_KR_API_KEY"] = api_key

    from web_app import app

    # 로컬 실행에서는 환경변수 전달 여부와 무관하게 Flask가 키를 직접 보관한다.
    app.config["DATA_GO_KR_API_KEY"] = api_key

    if not os.getenv("DATA_GO_KR_API_KEY"):
        raise SystemExit("인증키 설정에 실패했습니다.")

    print("인증키 설정 확인: OK")
    print("브라우저에서 http://127.0.0.1:8013 을 여세요.")
    print("서버를 끄려면 이 창에서 Ctrl+C를 누르세요.")
    app.run(host="0.0.0.0", port=8013, debug=False)


if __name__ == "__main__":
    main()
