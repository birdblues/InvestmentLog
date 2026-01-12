#!/bin/bash

PLIST_NAME_DEFAULT="com.birdblues.investmentlog.plist"
PLIST_NAME_DAEMON_DEFAULT="com.birdblues.investmentlog.daemon.plist"
DEST_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="./logs"
DAEMON_MODE=0

if [[ "$1" == "--daemon" ]]; then
  DAEMON_MODE=1
  shift
fi

if [[ "$1" == *.plist ]]; then
  PLIST_NAME="$1"
  ACTION="${2:-install}"
else
  PLIST_NAME="$PLIST_NAME_DEFAULT"
  ACTION="${1:-}"
fi

if [[ "$DAEMON_MODE" -eq 1 ]]; then
  DEST_DIR="/Library/LaunchDaemons"
  DOMAIN="system"
  if [[ "$PLIST_NAME" == "$PLIST_NAME_DEFAULT" ]]; then
    PLIST_NAME="$PLIST_NAME_DAEMON_DEFAULT"
  fi
else
  DOMAIN="gui/$(id -u)"
fi

DEST_FILE="$DEST_DIR/$PLIST_NAME"
LABEL="${PLIST_NAME%.plist}"

# Ensure log directory exists
if [ ! -d "$LOG_DIR" ]; then
  mkdir -p "$LOG_DIR"
  echo "📂 로그 디렉토리 생성됨: $LOG_DIR"
fi

case "$ACTION" in
install | start)
  echo "🚀 스케줄러 설치 및 시작 중..."
  if [[ "$DAEMON_MODE" -eq 1 ]]; then
    sudo cp "$PLIST_NAME" "$DEST_FILE"
    sudo chown root:wheel "$DEST_FILE"
    sudo chmod 644 "$DEST_FILE"
    sudo launchctl bootout "$DOMAIN" "$DEST_FILE" 2>/dev/null
    sudo launchctl bootstrap "$DOMAIN" "$DEST_FILE"
    sudo launchctl kickstart -k "$DOMAIN/$LABEL"
  else
    cp "$PLIST_NAME" "$DEST_FILE"
    # macOS 최신 방식: bootout -> bootstrap -> kickstart
    launchctl bootout "$DOMAIN" "$DEST_FILE" 2>/dev/null
    launchctl bootstrap "$DOMAIN" "$DEST_FILE"
    launchctl kickstart -k "$DOMAIN/$LABEL"
  fi
  echo "✅ 설치 완료!"
  echo "   로그 확인: $LOG_DIR/stdout.log"
  ;;
uninstall | stop)
  echo "🛑 스케줄러 중지 및 제거 중..."
  if [[ "$DAEMON_MODE" -eq 1 ]]; then
    sudo launchctl bootout "$DOMAIN" "$DEST_FILE" 2>/dev/null
    sudo rm -f "$DEST_FILE"
  else
    launchctl bootout "$DOMAIN" "$DEST_FILE" 2>/dev/null
    rm -f "$DEST_FILE"
  fi
  echo "✅ 제거 완료."
  ;;
status)
  echo "📊 스케줄러 상태 확인:"
  if [[ "$DAEMON_MODE" -eq 1 ]]; then
    sudo launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1
  else
    launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1
  fi
  if [ $? -eq 0 ]; then
    echo "✅ 서비스가 등록되어 있습니다."
  else
    echo "⚠️ 서비스가 등록되어 있지 않습니다."
  fi
  ;;
*)
  echo "사용법: $0 [--daemon] [plist] {install|uninstall|status}"
  exit 1
  ;;
esac
