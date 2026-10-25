"""Writes plugins\\ApocryphaAgentControl\\translations\\<language>.txt from the table below ($KEY<TAB>text, UTF-16LE with a
BOM, CRLF - the shape the plugin's TR() reads). The table is the one place a string's eleven languages are kept;
re-run after changing it:  python tools\\make_translations.py"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "plugins", "ApocryphaAgentControl", "translations")
LANGS = ("english", "japanese", "korean", "chinese", "russian", "german", "french", "spanish", "italian", "polish", "czech")

S = {
    "AC_Description": (
        "A command channel on this computer only (127.0.0.1, a new secret token each session) that lets scripts, tools and AI agents operate MO2 without clicking on its window.",
        "このコンピューター内だけのコマンドチャンネル（127.0.0.1、セッションごとに新しい秘密トークン）。スクリプト、ツール、AI エージェントが MO2 のウィンドウをクリックせずに MO2 を操作できます。",
        "이 컴퓨터 안에서만 쓰는 명령 채널(127.0.0.1, 세션마다 새 비밀 토큰)로, 스크립트·도구·AI 에이전트가 MO2 창을 클릭하지 않고 MO2를 조작할 수 있습니다.",
        "仅限本机的命令通道（127.0.0.1，每次会话一个新的秘密令牌），让脚本、工具和 AI 代理无需点击 MO2 窗口即可操作 MO2。",
        "Канал команд только на этом компьютере (127.0.0.1, новый секретный токен в каждом сеансе), через который скрипты, инструменты и ИИ-агенты управляют MO2 без щелчков по его окну.",
        "Ein Befehlskanal nur auf diesem Computer (127.0.0.1, in jeder Sitzung ein neues geheimes Token), über den Skripte, Werkzeuge und KI-Agenten MO2 bedienen, ohne in sein Fenster zu klicken.",
        "Un canal de commandes limité à cet ordinateur (127.0.0.1, un nouveau jeton secret à chaque session) qui permet aux scripts, outils et agents IA de piloter MO2 sans cliquer dans sa fenêtre.",
        "Un canal de órdenes solo en este equipo (127.0.0.1, un token secreto nuevo en cada sesión) que permite a scripts, herramientas y agentes de IA manejar MO2 sin hacer clic en su ventana.",
        "Un canale di comandi solo su questo computer (127.0.0.1, un nuovo token segreto a ogni sessione) che permette a script, strumenti e agenti IA di usare MO2 senza cliccare nella sua finestra.",
        "Kanał poleceń tylko na tym komputerze (127.0.0.1, nowy tajny token w każdej sesji), przez który skrypty, narzędzia i agenci AI obsługują MO2 bez klikania w jego okno.",
        "Kanál příkazů jen na tomto počítači (127.0.0.1, v každé relaci nový tajný token), přes který skripty, nástroje a agenti AI ovládají MO2 bez klikání do jeho okna.",
    ),
    "AC_DisplayName": (
        "Agent Control", "エージェント制御", "에이전트 제어", "代理控制", "Управление агентами", "Agentensteuerung",
        "Contrôle des agents", "Control de agentes", "Controllo agenti", "Sterowanie agentami", "Ovládání agentů",
    ),
    "AC_Tooltip": (
        "Shows whether the command channel is listening",
        "コマンドチャンネルが待ち受け中かどうかを表示します",
        "명령 채널이 대기 중인지 보여 줍니다",
        "显示命令通道是否正在监听",
        "Показывает, слушает ли канал команд",
        "Zeigt, ob der Befehlskanal empfangsbereit ist",
        "Indique si le canal de commandes est à l'écoute",
        "Muestra si el canal de órdenes está escuchando",
        "Mostra se il canale di comandi è in ascolto",
        "Pokazuje, czy kanał poleceń nasłuchuje",
        "Ukazuje, zda kanál příkazů naslouchá",
    ),
    "AC_SetRefuse": (
        "Refuse commands that change anything while you are using MO2 (its window in front, keyboard or mouse used recently). Reading is always allowed.",
        "MO2 を使用中（ウィンドウが前面にあり、最近キーボードかマウスを使った）は、何かを変更するコマンドを拒否します。読み取りは常に許可されます。",
        "MO2를 사용 중일 때(창이 맨 앞에 있고 최근에 키보드나 마우스를 사용함) 무언가를 바꾸는 명령을 거부합니다. 읽기는 항상 허용됩니다.",
        "当你正在使用 MO2（其窗口在最前面，且最近用过键盘或鼠标）时，拒绝会改动任何内容的命令。读取始终允许。",
        "Отклонять команды, которые что-либо меняют, пока вы пользуетесь MO2 (его окно впереди, клавиатура или мышь недавно использовались). Чтение разрешено всегда.",
        "Befehle ablehnen, die etwas ändern, während Sie MO2 benutzen (sein Fenster im Vordergrund, Tastatur oder Maus kürzlich benutzt). Lesen ist immer erlaubt.",
        "Refuser les commandes qui modifient quelque chose pendant que vous utilisez MO2 (sa fenêtre au premier plan, clavier ou souris utilisés récemment). La lecture est toujours autorisée.",
        "Rechazar las órdenes que cambian algo mientras usas MO2 (su ventana al frente, teclado o ratón usados hace poco). La lectura siempre está permitida.",
        "Rifiuta i comandi che modificano qualcosa mentre usi MO2 (la sua finestra in primo piano, tastiera o mouse usati di recente). La lettura è sempre consentita.",
        "Odrzucaj polecenia, które cokolwiek zmieniają, gdy używasz MO2 (jego okno na wierzchu, klawiatura lub mysz użyte niedawno). Odczyt jest zawsze dozwolony.",
        "Odmítat příkazy, které cokoli mění, když MO2 používáte (jeho okno je vpředu, klávesnice nebo myš byly nedávno použity). Čtení je povoleno vždy.",
    ),
    "AC_SetMinutes": (
        "How many minutes after your last keyboard or mouse input MO2 still counts as in use.",
        "最後のキーボードまたはマウス入力から何分間、MO2 を使用中とみなすか。",
        "마지막 키보드나 마우스 입력 후 몇 분 동안 MO2를 사용 중으로 볼지 정합니다.",
        "最后一次键盘或鼠标输入后，MO2 在多少分钟内仍算作正在使用。",
        "Сколько минут после последнего ввода с клавиатуры или мыши MO2 ещё считается используемым.",
        "Wie viele Minuten nach Ihrer letzten Tastatur- oder Mauseingabe MO2 noch als in Benutzung gilt.",
        "Combien de minutes après votre dernière saisie au clavier ou à la souris MO2 est encore considéré comme utilisé.",
        "Cuántos minutos después de tu última entrada de teclado o ratón se sigue considerando que MO2 está en uso.",
        "Per quanti minuti dopo l'ultimo input da tastiera o mouse MO2 è ancora considerato in uso.",
        "Ile minut po ostatnim użyciu klawiatury lub myszy MO2 wciąż uznaje się za używany.",
        "Kolik minut po posledním vstupu z klávesnice nebo myši se MO2 stále počítá jako používaný.",
    ),
    "AC_SetActivity": (
        "Optional: a JSON file another tool keeps up to date with your last real input (last_input_epoch, alive_epoch). Empty uses Windows' idle clock.",
        "任意：別のツールが最後の実際の入力を書き続ける JSON ファイル（last_input_epoch、alive_epoch）。空欄なら Windows のアイドル時間を使います。",
        "선택 사항: 다른 도구가 마지막 실제 입력을 계속 기록하는 JSON 파일(last_input_epoch, alive_epoch). 비워 두면 Windows의 유휴 시간을 사용합니다.",
        "可选：由另一个工具持续更新你最后一次真实输入的 JSON 文件（last_input_epoch、alive_epoch）。留空则使用 Windows 的空闲计时。",
        "Необязательно: JSON-файл, в котором другой инструмент отмечает ваш последний реальный ввод (last_input_epoch, alive_epoch). Пусто — используются часы простоя Windows.",
        "Optional: eine JSON-Datei, in der ein anderes Werkzeug Ihre letzte echte Eingabe festhält (last_input_epoch, alive_epoch). Leer nutzt die Leerlaufuhr von Windows.",
        "Facultatif : un fichier JSON qu'un autre outil tient à jour avec votre dernière vraie saisie (last_input_epoch, alive_epoch). Vide : l'horloge d'inactivité de Windows est utilisée.",
        "Opcional: un archivo JSON que otra herramienta mantiene al día con tu última entrada real (last_input_epoch, alive_epoch). Vacío usa el reloj de inactividad de Windows.",
        "Facoltativo: un file JSON che un altro strumento tiene aggiornato con il tuo ultimo input reale (last_input_epoch, alive_epoch). Vuoto usa l'orologio di inattività di Windows.",
        "Opcjonalnie: plik JSON, w którym inne narzędzie zapisuje Twoje ostatnie prawdziwe użycie (last_input_epoch, alive_epoch). Puste używa zegara bezczynności Windows.",
        "Volitelné: soubor JSON, do kterého jiný nástroj zapisuje váš poslední skutečný vstup (last_input_epoch, alive_epoch). Prázdné použije hodiny nečinnosti Windows.",
    ),
    "AC_Listening": (
        "Listening on 127.0.0.1:{port} for mo2-ctl and other clients.\\n\\nChannel file:\\n{path}",
        "127.0.0.1:{port} で mo2-ctl などのクライアントを待ち受けています。\\n\\nチャンネルファイル：\\n{path}",
        "127.0.0.1:{port}에서 mo2-ctl 및 다른 클라이언트를 기다리는 중입니다.\\n\\n채널 파일:\\n{path}",
        "正在 127.0.0.1:{port} 上为 mo2-ctl 和其他客户端监听。\\n\\n通道文件：\\n{path}",
        "Ожидание mo2-ctl и других клиентов на 127.0.0.1:{port}.\\n\\nФайл канала:\\n{path}",
        "Empfangsbereit auf 127.0.0.1:{port} für mo2-ctl und andere Clients.\\n\\nKanaldatei:\\n{path}",
        "À l'écoute sur 127.0.0.1:{port} pour mo2-ctl et les autres clients.\\n\\nFichier du canal :\\n{path}",
        "Escuchando en 127.0.0.1:{port} para mo2-ctl y otros clientes.\\n\\nArchivo del canal:\\n{path}",
        "In ascolto su 127.0.0.1:{port} per mo2-ctl e altri client.\\n\\nFile del canale:\\n{path}",
        "Nasłuchuje na 127.0.0.1:{port} dla mo2-ctl i innych klientów.\\n\\nPlik kanału:\\n{path}",
        "Naslouchá na 127.0.0.1:{port} pro mo2-ctl a další klienty.\\n\\nSoubor kanálu:\\n{path}",
    ),
    "AC_CheckOn": (
        "Changes are refused while you are using MO2.",
        "MO2 を使用中は変更が拒否されます。",
        "MO2를 사용하는 동안에는 변경이 거부됩니다.",
        "你正在使用 MO2 时，更改会被拒绝。",
        "Пока вы пользуетесь MO2, изменения отклоняются.",
        "Solange Sie MO2 benutzen, werden Änderungen abgelehnt.",
        "Les modifications sont refusées pendant que vous utilisez MO2.",
        "Los cambios se rechazan mientras usas MO2.",
        "Le modifiche vengono rifiutate mentre usi MO2.",
        "Zmiany są odrzucane, gdy używasz MO2.",
        "Když MO2 používáte, změny jsou odmítnuty.",
    ),
    "AC_CheckOff": (
        "The in-use check is off: changes are always accepted.",
        "使用中チェックはオフです：変更は常に受け付けられます。",
        "사용 중 확인이 꺼져 있습니다: 변경은 항상 받아들여집니다.",
        "使用中检查已关闭：更改始终会被接受。",
        "Проверка использования выключена: изменения принимаются всегда.",
        "Die Benutzungsprüfung ist aus: Änderungen werden immer angenommen.",
        "La vérification d'utilisation est désactivée : les modifications sont toujours acceptées.",
        "La comprobación de uso está desactivada: los cambios siempre se aceptan.",
        "Il controllo d'uso è disattivato: le modifiche vengono sempre accettate.",
        "Sprawdzanie użycia jest wyłączone: zmiany są zawsze przyjmowane.",
        "Kontrola používání je vypnutá: změny jsou vždy přijaty.",
    ),
    "AC_NotListening": (
        "Not listening - see the log in plugins\\data\\{name}\\log.txt.",
        "待ち受けていません - plugins\\data\\{name}\\log.txt のログを確認してください。",
        "대기 중이 아닙니다 - plugins\\data\\{name}\\log.txt의 로그를 확인하세요.",
        "未在监听 - 请查看 plugins\\data\\{name}\\log.txt 中的日志。",
        "Не слушает — см. журнал plugins\\data\\{name}\\log.txt.",
        "Nicht empfangsbereit - siehe das Protokoll in plugins\\data\\{name}\\log.txt.",
        "Pas à l'écoute - voir le journal dans plugins\\data\\{name}\\log.txt.",
        "No está escuchando: consulta el registro en plugins\\data\\{name}\\log.txt.",
        "Non in ascolto - vedi il log in plugins\\data\\{name}\\log.txt.",
        "Nie nasłuchuje - zobacz dziennik w plugins\\data\\{name}\\log.txt.",
        "Nenaslouchá - viz protokol v plugins\\data\\{name}\\log.txt.",
    ),
}

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for i, lang in enumerate(LANGS):
        lines = ["$%s\t%s" % (k, v[i]) for k, v in S.items()]
        with open(os.path.join(OUT, lang + ".txt"), "wb") as f:
            f.write(b"\xff\xfe" + ("\r\n".join(lines) + "\r\n").encode("utf-16-le"))
    print("wrote %d languages x %d strings to %s" % (len(LANGS), len(S), os.path.normpath(OUT)))
