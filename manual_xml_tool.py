# manual_xml_tool.py
# PyQt6 GUI voor TQS LM – auto version negotiation + Order Build
# - Query Version bij opstart -> vult TNT version, dbVersion & namespace
# - Articles -> Fields (toon standaard enkel vereiste invulvelden)
# - Constraint-validatie (regex type 27, interval type 25, GS1/IFA type 10)
# - Create Order (auto-version) + optionele SNS
# - Start Order (auto-version)
# - Werkt met Python 3.12 en PyQt6

# [SECTION: Imports]
from __future__ import annotations

import sys, socket, base64, zlib, datetime, traceback, re
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET
from pathlib import Path

from PyQt6 import QtWidgets, QtCore, QtGui



# [END: Imports]
# [FUNC: iso_now]
def iso_now() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .astimezone()
        .isoformat(timespec="seconds")
    )

# [END: iso_now]

# [FUNC: xml_escape]
def xml_escape(s: str | None) -> str:
    if not s:
        return ""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )

# [END: xml_escape]

# [FUNC: strip_ns]
def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if tag.startswith("{") else tag

# [END: strip_ns]

# [FUNC: build_sns_payload_for_level]
def build_sns_payload_for_level(level_id: int) -> tuple[str, int]:
    """Genereer 10 SN's (01..10) voor level_id; geef base64(DEFLATE(xml)), uncompressed-length."""
    nums = [f"{i:02d}" for i in range(1, 11)]
    inner = (
        f"<lvl><id>{level_id}</id>"
        + "".join(f"<sn><no>{n}</no></sn>" for n in nums)
        + "</lvl>"
    )
    raw = inner.encode("utf-8")
    comp = zlib.compress(raw)  # RFC1950 zlib (DEFLATE)
    return base64.b64encode(comp).decode("ascii"), len(raw)

# [END: build_sns_payload_for_level]



# [FUNC: parse_tnt_meta]
def parse_tnt_meta(xml_text: str) -> tuple[str, str, str, ET.Element]:
    root = ET.fromstring(xml_text)
    ns = (
        root.tag[1:].split("}")[0]
        if root.tag.startswith("{")
        else (root.attrib.get("xmlns", "") or "http://www.wipotec.com")
    )
    tnt_version = root.attrib.get("version", "") or ""
    dbv = root.attrib.get("dbVersion", "") or ""
    return ns, tnt_version, dbv, root

# [END: parse_tnt_meta]

# [FUNC: parse_article_names]
def parse_article_names(xml_text: str) -> list[str]:
    names: list[str] = []
    try:
        root = ET.fromstring(xml_text)
        for el in root.iter():
            if strip_ns(el.tag) == "article":
                nm = next((c for c in el if strip_ns(c.tag) == "name"), None)
                if nm is not None and (nm.text or "").strip():
                    names.append(nm.text.strip())
    except Exception:
        pass
    return names

# [END: parse_article_names]

# [FUNC: parse_article_fields]
def parse_article_fields(xml_text: str):
    """
    Geef lijst dicts terug:
      { 'level': int, 'name': str, 'display': str|None, 'writable': bool, 'preset': str|None }
    Werkt namespace-agnostisch en pakt elk veld dat directe children <name> en <display-name> heeft.
    Level wordt bepaald via dichtstbijzijnde ancestor <aggregation-level><id>.
    """
    def strip_ns(tag: str) -> str:
        return tag.split("}", 1)[1] if tag.startswith("{") else tag

    rows = []
    try:
        root = ET.fromstring(xml_text)

        # Vind <response> (maakt niet uit welke xsi:type)
        response = None
        for el in root.iter():
            if strip_ns(el.tag) == "response":
                response = el
                break
        if response is None:
            return rows

        # Helper om level te bepalen via ancestor aggregation-level/id
        def level_for(node: ET.Element) -> int:
            p = node
            while p is not None:
                if strip_ns(p.tag) == "aggregation-level":
                    for ch in p:
                        if strip_ns(ch.tag) == "id" and (ch.text or "").strip().isdigit():
                            return int(ch.text.strip())
                p = p.getparent() if hasattr(p, "getparent") else None  # ElementTree heeft dit niet standaard
            # fallback zonder getparent(): loop opnieuw via handmatige climb
            # (we lopen lineair omhoog door elke parent via een stack)
            # ElementTree heeft geen parent link, dus we doen een tweede pass:
            return 1  # veilige default

        # Omdat ElementTree geen parent heeft, bepalen we level via tweede pass:
        # We lopen alle aggregation-levels af en merken hun children.
        level_map = {}
        for agg in response.iter():
            if strip_ns(agg.tag) == "aggregation-level":
                lvl = 1
                for ch in agg:
                    if strip_ns(ch.tag) == "id" and (ch.text or "").strip().isdigit():
                        lvl = int(ch.text.strip())
                        break
                # markeer alle subnodes van deze aggregation-level met dit level-id
                for sub in agg.iter():
                    level_map[id(sub)] = lvl

        # Pak elk element dat DIRECTE kinderen <name> en <display-name> heeft
        for node in response.iter():
            # verzamel directe kinderen
            name_text = None
            disp_text = None
            writable = None
            preset = None
            for ch in list(node):
                local = strip_ns(ch.tag)
                if local == "name":
                    name_text = (ch.text or "").strip()
                elif local == "display-name":
                    disp_text = (ch.text or "").strip()
                elif local == "writable":
                    writable = (ch.text or "").strip()
                elif local in ("value-set-by-article", "preset", "default-value"):
                    preset = (ch.text or "").strip()
            if name_text is None or disp_text is None:
                continue  # geen echt veld

            lvl = level_map.get(id(node), 1)
            is_writable = True
            if writable is not None:
                is_writable = writable.lower() not in ("0", "false", "no")

            rows.append({
                "level": lvl,
                "name": name_text,
                "display": disp_text,
                "writable": is_writable,
                "preset": preset,
            })
    except Exception:
        pass
    return rows

# [END: parse_article_fields]


# [CLASS: TQSClient]
class TQSClient(QtCore.QObject):
    received = QtCore.pyqtSignal(str)

# [FUNC: __init__]
    def __init__(self, host: str, port: int, timeout=20.0):
        super().__init__()
        self.host, self.port, self.timeout = host, port, timeout
        self.sock: Optional[socket.socket] = None

# [END: __init__]
# [FUNC: connect]
    def connect(self):
        if self.sock:
            self.close()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect((self.host, self.port))
        s.settimeout(self.timeout)
        self.sock = s

# [END: connect]
# [FUNC: close]
    def close(self):
        try:
            if self.sock:
                self.sock.close()
        finally:
            self.sock = None

# [END: close]
# [FUNC: send_and_recv]
    def send_and_recv(self, xml_text: str) -> str:
        if not self.sock:
            self.connect()
        self.sock.sendall(xml_text.encode("utf-8"))
        chunks = []
        while True:
            try:
                b = self.sock.recv(65536)
                if not b:
                    break
                chunks.append(b)
                if b"</tnt>" in b"".join(chunks):
                    break
            except socket.timeout:
                break
        text = b"".join(chunks).decode("utf-8", errors="replace")
        self.received.emit(text)
        return text

# [END: send_and_recv]
# [END: TQSClient]



# [CLASS: ManualTool]
class ManualTool(QtWidgets.QWidget):
# [FUNC: __init__]
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TQS Manual XML Tool + Order Builder (Auto-Version)")
        self.resize(1320, 860)

        # Connection & protocol
        self.edHost = QtWidgets.QLineEdit("192.168.0.70")
        self.edPort = QtWidgets.QLineEdit("7973")
        self.edAgent = QtWidgets.QLineEdit("MW")
        self.edIface = QtWidgets.QLineEdit("1.15")
        self.edDB = QtWidgets.QLineEdit("")
        self.edNS = QtWidgets.QLineEdit("http://www.wipotec.com")

        f = QtWidgets.QFormLayout()
        f.addRow("Host:", self.edHost)
        f.addRow("Port:", self.edPort)
        f.addRow("Agent:", self.edAgent)
        f.addRow("TNT version (client):", self.edIface)
        f.addRow("DB version:", self.edDB)
        f.addRow("XML Namespace:", self.edNS)

        btnConnect = QtWidgets.QPushButton("Test connect")
        btnConnect.clicked.connect(self.on_test_connect)
        btnQuery = QtWidgets.QPushButton("Query Version (auto)")
        btnQuery.clicked.connect(self.on_query_version)

        hb = QtWidgets.QHBoxLayout()
        hb.addWidget(btnConnect)
        hb.addWidget(btnQuery)
        hb.addStretch(1)

        grpConn = QtWidgets.QGroupBox("Connection & Protocol")
        vbConn = QtWidgets.QVBoxLayout(grpConn)
        vbConn.addLayout(f)
        vbConn.addLayout(hb)

        # Manual XML
        self.edXML = QtWidgets.QPlainTextEdit(
            '<request xsi:type="get-article-data-request" version="1.0" id="1">\n  <article-name>Article 1</article-name>\n  <get-all-data />\n  <include-child-count />\n</request>'
        )
        btnSend = QtWidgets.QPushButton("Send manual request")
        btnSend.clicked.connect(self.on_send_manual)
        grpManual = QtWidgets.QGroupBox("Manual XML")
        vbMan = QtWidgets.QVBoxLayout(grpManual)
        vbMan.addWidget(self.edXML)
        vbMan.addWidget(btnSend)

        # Raw log
        self.edRaw = QtWidgets.QPlainTextEdit()
        self.edRaw.setReadOnly(True)
        grpRaw = QtWidgets.QGroupBox("Raw in/out")
        vbRaw = QtWidgets.QVBoxLayout(grpRaw)
        vbRaw.addWidget(self.edRaw)

        # Articles
        self.btnGetArticles = QtWidgets.QPushButton("Get article list")
        self.btnGetArticles.clicked.connect(self.on_get_articles)
        self.btnGetFields = QtWidgets.QPushButton("Get fields for selected")
        self.btnGetFields.clicked.connect(self.on_get_fields)
        self.listArticles = QtWidgets.QListWidget()
        self.listArticles.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        hbArt = QtWidgets.QHBoxLayout()
        hbArt.addWidget(self.btnGetArticles)
        hbArt.addWidget(self.btnGetFields)
        grpArt = QtWidgets.QGroupBox("Articles")
        vbArt = QtWidgets.QVBoxLayout(grpArt)
        vbArt.addLayout(hbArt)
        vbArt.addWidget(self.listArticles)

        # Fields + Order
        self.fieldsView = QtWidgets.QTreeWidget()
        self.fieldsView.setHeaderLabels(
            ["Level", "Name", "Display-name", "Writable", "Preset/Value"]
        )
        self.fieldsView.setColumnWidth(0, 60)
        self.fieldsView.setColumnWidth(1, 380)
        self.fieldsView.setColumnWidth(2, 220)
        self.fieldsView.setColumnWidth(3, 80)

        self.chkRequiredOnly = QtWidgets.QCheckBox(
            "Toon enkel verplichte invulvelden (writable=1 zonder preset)"
        )
        self.chkRequiredOnly.setChecked(True)
        self.chkAllFields = QtWidgets.QCheckBox("Vraag alle fields op (get-all-fields)")
        self.chkAllFields.setChecked(False)

        self.edOrderName = QtWidgets.QLineEdit("TestOrder001")
        self.chkIncludeSN = QtWidgets.QCheckBox("Include 10 serial numbers (01..10)")
        self.chkIncludeSN.setChecked(True)

        btnCreate = QtWidgets.QPushButton("CREATE ORDER (auto-version)")
        btnImport = QtWidgets.QPushButton("IMPORT ORDER (auto-version)")
        btnStart = QtWidgets.QPushButton("START ORDER (auto-version)")
        btnCreate.clicked.connect(self.on_send_create_order)
        btnImport.clicked.connect(self.on_send_import_order)
        btnStart.clicked.connect(self.on_start_order)

        grpOrder = QtWidgets.QGroupBox("Order builder")
        vbOrder = QtWidgets.QVBoxLayout(grpOrder)
        vbOrder.addWidget(self.chkRequiredOnly)
        vbOrder.addWidget(self.chkAllFields)
        vbOrder.addWidget(self.fieldsView, 1)
        formOrder = QtWidgets.QFormLayout()
        formOrder.addRow("Order name:", self.edOrderName)
        vbOrder.addLayout(formOrder)
        vbOrder.addWidget(self.chkIncludeSN)
        hbOrder = QtWidgets.QHBoxLayout()
        hbOrder.addWidget(btnCreate)
        hbOrder.addWidget(btnImport)
        hbOrder.addWidget(btnStart)
        hbOrder.addStretch(1)
        vbOrder.addLayout(hbOrder)

        # Layout
        left = QtWidgets.QVBoxLayout()
        left.addWidget(grpConn)
        left.addWidget(grpArt)
        left.addWidget(grpOrder, 1)
        right = QtWidgets.QVBoxLayout()
        right.addWidget(grpManual, 1)
        right.addWidget(grpRaw, 1)
        sp = QtWidgets.QSplitter()
        leftW = QtWidgets.QWidget()
        leftW.setLayout(left)
        rightW = QtWidgets.QWidget()
        rightW.setLayout(right)
        sp.addWidget(leftW)
        sp.addWidget(rightW)
        sp.setSizes([660, 660])
        root = QtWidgets.QHBoxLayout(self)
        root.addWidget(sp)

        self.client: TQSClient | None = None
        self.current_fields: list[dict] = []
        self.current_article: str | None = None
        self.last_created_order: str | None = None

        # Auto query version bij opstart
        QtCore.QTimer.singleShot(0, self.on_query_version)

# [END: __init__]

# [FUNC: client_or_new]
    def client_or_new(self) -> TQSClient:
        host = self.edHost.text().strip() or "127.0.0.1"
        port = int(self.edPort.text().strip() or "7973")
        if self.client and (self.client.host != host or self.client.port != port):
            self.client.close()
            self.client = None
        if not self.client:
            self.client = TQSClient(host, port, timeout=20.0)
            self.client.received.connect(self.on_received)
        return self.client

# [END: client_or_new]
# [FUNC: current_ns]
    def current_ns(self) -> str:
        return self.edNS.text().strip() or "http://www.wipotec.com"

# [END: current_ns]
# [FUNC: iface_ver]
    def iface_ver(self) -> str:
        return self.edIface.text().strip() or "1.15"

# [END: iface_ver]
# [FUNC: db_ver]
    def db_ver(self) -> str | None:
        v = self.edDB.text().strip()
        return v if v else None

# [END: db_ver]
# [FUNC: agent]
    def agent(self) -> str:
        return self.edAgent.text().strip() or "MW"

# [END: agent]
# [FUNC: build_tnt]
    def build_tnt(self, inner_xml: str) -> str:
        db_attr = f' dbVersion="{xml_escape(self.db_ver())}"' if self.db_ver() else ""
        return (
            f'<tnt version="{xml_escape(self.iface_ver())}"{db_attr} '
            f'xmlns="{xml_escape(self.current_ns())}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f"<header><agent>{xml_escape(self.agent())}</agent><timestamp>{iso_now()}</timestamp></header>"
            f"{inner_xml}"
            f"</tnt>"
        )

# [END: build_tnt]
# [FUNC: append_raw]
    def append_raw(self, text: str):
        self.edRaw.appendPlainText(text)

# [END: append_raw]

# [FUNC: send_inner]
    def send_inner(self, inner_xml: str) -> str:
        env = self.build_tnt(inner_xml)
        self.append_raw(f">>> SENT @ {iso_now()}\n{env}\n")
        resp = self.client_or_new().send_and_recv(env)
        self.append_raw(f"<<< RECV @ {iso_now()}\n{resp}\n")
        return resp

# [END: send_inner]
# [FUNC: negotiate_and_send]
    def negotiate_and_send(
        self, xsi_type: str, candidates: list[str], body_builder
    ) -> str:
        last_resp = ""
        tried = []
        for ver in candidates:
            tried.append(ver)
            inner = body_builder(ver)
            last_resp = self.send_inner(inner)
            if "version-error" in last_resp:
                m = re.search(r"<concerning>([^<]+)</concerning>", last_resp)
                if m:
                    want = m.group(1).strip()
                    if want and want not in tried:
                        inner2 = body_builder(want)
                        last_resp = self.send_inner(inner2)
                        if "version-error" in last_resp:
                            continue
                        return last_resp
                continue
            return last_resp
        return last_resp

# [END: negotiate_and_send]

# [FUNC: on_test_connect]
    def on_test_connect(self):
        try:
            c = self.client_or_new()
            c.connect()
            self.append_raw(f"# Connected to {c.host}:{c.port}")
        except Exception as e:
            self.append_raw(f"# Connect failed: {e}\n{traceback.format_exc()}")

# [END: on_test_connect]
# [FUNC: on_query_version]
    def on_query_version(self):
        # Doc: request 1.0; response kan 2.0 zijn en bevat versies/DB/namespace. :contentReference[oaicite:6]{index=6}
        candidates = ["1.0", "1.1", "2.0"]

        def builder(v: str) -> str:
            return f'<request xsi:type="query-version-request" version="{v}" id="1" />'

        resp = self.negotiate_and_send("query-version-request", candidates, builder)
        try:
            ns, tnt_v, dbv, _ = parse_tnt_meta(resp)
            if tnt_v:
                self.edIface.setText(tnt_v)
            if dbv:
                self.edDB.setText(dbv)
            if ns:
                self.edNS.setText(ns)
        except Exception:
            pass

# [END: on_query_version]
# [FUNC: on_send_manual]
    def on_send_manual(self):
        inner = self.edXML.toPlainText().strip()
        if not inner.startswith("<request"):
            QtWidgets.QMessageBox.warning(
                self, "Manual", "Plaats een <request>...</request> in het veld."
            )
            return
        try:
            self.send_inner(inner)
        except Exception as e:
            self.append_raw(f"# Manual send failed: {e}\n{traceback.format_exc()}")

# [END: on_send_manual]
# [FUNC: on_get_articles]
    def on_get_articles(self):
        # Spec zegt: 1.0 (we onderhandelen toch) :contentReference[oaicite:7]{index=7}
        candidates = ["2.0", "1.1", "1.0"]

        def builder(v: str) -> str:
            return (
                f'<request xsi:type="get-article-list-request" version="{v}" id="1" />'
            )

        try:
            resp = self.negotiate_and_send(
                "get-article-list-request", candidates, builder
            )
            names = parse_article_names(resp)
            self.listArticles.clear()
            for n in names:
                self.listArticles.addItem(n)
        except Exception as e:
            self.append_raw(f"# Get-article-list failed: {e}\n{traceback.format_exc()}")

# [END: on_get_articles]
# [FUNC: on_get_fields]
    def on_get_fields(self):
        sel = self.listArticles.currentItem()
        if not sel:
            QtWidgets.QMessageBox.information(self, "Fields", "Selecteer eerst een artikel.")
            return
        art = sel.text()
        self.current_article = art
        inner = (
            '<request xsi:type="get-article-fields-request" version="1.0" id="1">\n'
            f'  <article-name>{xml_escape(art)}</article-name>\n'
            '</request>'
        )
        try:
            resp = self.send_req(inner)
            fields = parse_article_fields(resp)
            if not fields:
                # fallback: toch nog eens brute-force proberen (sommige LMs gebruiken andere response-typen)
                fields = parse_article_fields(self.edRaw.toPlainText())
            if fields:
                self.current_fields = fields
                self.populate_fields_view(fields)
            else:
                QtWidgets.QMessageBox.information(self, "Fields", "Geen invulbare fields gevonden in de response.")
        except Exception as e:
            self.append_raw(f"# Get fields failed: {e}")

# [END: on_get_fields]
# [FUNC: _make_editor_for_constraints]
    def _make_editor_for_constraints(
        self, constraints: List[Dict[str, Any]]
    ) -> QtWidgets.QLineEdit:
        ed = QtWidgets.QLineEdit()
        # type 27 = regex
        rx_vals = [
            c["value"] for c in constraints if c.get("type") == 27 and c.get("value")
        ]
        if rx_vals:
            try:
                rx = QtCore.QRegularExpression(rx_vals[0])
                ed.setValidator(QtGui.QRegularExpressionValidator(rx))
                ed.setPlaceholderText(f"regex: {rx_vals[0]}")
                return ed
            except Exception:
                pass
        # type 25 = (min max)
        rng = next(
            (c for c in constraints if c.get("type") == 25 and c.get("value")), None
        )
        if rng:
            m = re.match(r"\(\s*(-?\d+)\s+(-?\d+)\s*\)", rng["value"])
            if m:
                lo, hi = int(m.group(1)), int(m.group(2))
                ed.setValidator(QtGui.QIntValidator(lo, hi))
                ed.setPlaceholderText(f"int {lo}..{hi}")
                return ed
        # type 10 (GS1/IFA) → enkel “niet leeg”
        if any(c.get("type") == 10 for c in constraints):
            ed.setPlaceholderText("vereist (GS1/IFA)")
        else:
            ed.setPlaceholderText("value")
        return ed

# [END: _make_editor_for_constraints]
# [FUNC: populate_fields_tree]
    def populate_fields_tree(self, fields: list[dict]):
        self.fieldsView.clear()
        # filter: enkel invulbare zonder preset als checkbox aan staat
        if self.chkRequiredOnly.isChecked():
            fields = [f for f in fields if f.get("writable") and not f.get("preset")]
        # groepeer per level
        by_level: dict[int, list[dict]] = {}
        for f in fields:
            by_level.setdefault(int(f.get("level", 0)), []).append(f)
        for lvl in sorted(by_level.keys()):
            parent = QtWidgets.QTreeWidgetItem([str(lvl), "", "", "", ""])
            parent.setFirstColumnSpanned(True)
            self.fieldsView.addTopLevelItem(parent)
            for f in by_level[lvl]:
                it = QtWidgets.QTreeWidgetItem(parent)
                it.setText(0, str(lvl))
                it.setText(1, f.get("name", ""))
                it.setText(2, f.get("display", ""))
                it.setText(3, "yes" if f.get("writable", False) else "no")
                if f.get("writable", False):
                    editor = self._make_editor_for_constraints(f.get("constraints", []))
                    self.fieldsView.setItemWidget(it, 4, editor)
                else:
                    it.setText(4, f.get("preset", ""))
            parent.setExpanded(True)

# [END: populate_fields_tree]
# [FUNC: build_order_data_xml_from_tree]
    def build_order_data_xml_from_tree(self) -> tuple[str, list[int]]:
        all_levels = set()
        filled: dict[int, list[tuple[str, str]]] = {}
        for i in range(self.fieldsView.topLevelItemCount()):
            parent = self.fieldsView.topLevelItem(i)
            try:
                lvl = int(parent.text(0))
            except Exception:
                continue
            all_levels.add(lvl)
            for j in range(parent.childCount()):
                it = parent.child(j)
                if not it.text(3).lower().startswith("y"):
                    continue
                editor = self.fieldsView.itemWidget(it, 4)
                val = (
                    editor.text().strip()
                    if isinstance(editor, QtWidgets.QLineEdit)
                    else ""
                )
                if val == "":
                    continue
                name = it.text(1)
                filled.setdefault(lvl, []).append((name, val))
        if not all_levels:
            all_levels = {0}
        parts = ["<order-data>"]
        for lvl in sorted(all_levels):
            parts += [
                "  <aggregation-level>",
                f"    <id>{lvl}</id>",
                "    <data-field-values>",
            ]
            for name, val in filled.get(lvl, []):
                parts += [
                    "      <element>",
                    f"        <name>{xml_escape(name)}</name>",
                    f"        <value>{xml_escape(val)}</value>",
                    "      </element>",
                ]
            parts += ["    </data-field-values>", "  </aggregation-level>"]
        parts.append("</order-data>")
        return "\n".join(parts), sorted(all_levels)

# [END: build_order_data_xml_from_tree]
# [FUNC: build_sns_block_if_checked]
    def build_sns_block_if_checked(self, levels: list[int]) -> str:
        if not self.chkIncludeSN.isChecked():
            return ""
        target_level = next((lvl for lvl in levels if lvl > 0), 0)
        b64, uncl = build_sns_payload_for_level(target_level)
        return f'<sns compression="DEFLATE" uncompressed-length="{uncl}">{b64}</sns>'

# [END: build_sns_block_if_checked]

# [FUNC: on_send_create_order]
    def on_send_create_order(self):
        if not self.current_article:
            QtWidgets.QMessageBox.information(
                self,
                "Create order",
                "Selecteer eerst een artikel en haal de fields op.",
            )
            return
        order_name = self.edOrderName.text().strip() or "TestOrder001"
        order_data_xml, levels = self.build_order_data_xml_from_tree()
        sns_xml = self.build_sns_block_if_checked(levels)
        # Doc: create-order heeft versies 1.0..1.2; 1.2 laat creëren tijdens lopend order. :contentReference[oaicite:9]{index=9}
        candidates = ["2.0", "1.2", "1.1", "1.0"]

        def builder(v: str) -> str:
            return (
                f'<request xsi:type="create-order-request" version="{v}" id="1">\n'
                f"  <order-name>{xml_escape(order_name)}</order-name>\n"
                f"  <article-name>{xml_escape(self.current_article)}</article-name>\n"
                f"{order_data_xml}\n"
                f"  {sns_xml}\n"
                f"</request>"
            )

        try:
            resp = self.negotiate_and_send("create-order-request", candidates, builder)
            self.last_created_order = (
                order_name if "<return-value>ok</return-value>" in resp else None
            )
        except Exception as e:
            self.append_raw(f"# Create order failed: {e}\n{traceback.format_exc()}")

# [END: on_send_create_order]
# [FUNC: on_send_import_order]
    def on_send_import_order(self):
        if not self.current_article:
            QtWidgets.QMessageBox.information(
                self,
                "Import order",
                "Selecteer eerst een artikel en haal de fields op.",
            )
            return
        order_name = self.edOrderName.text().strip() or "TestOrder001"
        order_data_xml, levels = self.build_order_data_xml_from_tree()
        sns_xml = self.build_sns_block_if_checked(levels)
        candidates = ["2.0", "1.2", "1.1", "1.0"]

        def builder(v: str) -> str:
            indented = order_data_xml.replace(
                "<order-data>", "    <order-data>"
            ).replace("</order-data>", "    </order-data>")
            return (
                f'<request xsi:type="import-order-request" version="{v}" id="1">\n'
                f'  <order version="2.0">\n'
                f"    <name>{xml_escape(order_name)}</name>\n"
                f"    <article-name>{xml_escape(self.current_article)}</article-name>\n"
                f"{indented}\n"
                f"    {sns_xml}\n"
                f"  </order>\n"
                f"</request>"
            )

        try:
            resp = self.negotiate_and_send("import-order-request", candidates, builder)
            self.last_created_order = (
                order_name if "<return-value>ok</return-value>" in resp else None
            )
        except Exception as e:
            self.append_raw(f"# Import order failed: {e}\n{traceback.format_exc()}")

# [END: on_send_import_order]
# [FUNC: on_start_order]
    def on_start_order(self):
        order_name = self.edOrderName.text().strip() or self.last_created_order or ""
        if not order_name:
            QtWidgets.QMessageBox.information(
                self,
                "Start order",
                "Geen ordernaam. Maak of importeer eerst een order.",
            )
            return
        # Doc: start-order-request wordt met version 1.0 getoond. :contentReference[oaicite:10]{index=10}
        candidates = ["2.0", "1.1", "1.0"]

        def builder(v: str) -> str:
            return (
                f'<request xsi:type="start-order-request" version="{v}" id="1">\n'
                f"  <order-name>{xml_escape(order_name)}</order-name>\n"
                f"</request>"
            )

        try:
            self.negotiate_and_send("start-order-request", candidates, builder)
        except Exception as e:
            self.append_raw(f"# Start order failed: {e}\n{traceback.format_exc()}")

# [END: on_start_order]

# [FUNC: on_received]
    def on_received(self, xml_text: str):
        # Raw log
        self.edRaw.appendPlainText(f"<<< RECV @ {iso_now()}\n{xml_text}\n")
        try:
            # 1) Als er artikelen in zitten → lijst vullen
            if "<article>" in xml_text and ("get-article-list-response" in xml_text or "get-" in xml_text):
                names = parse_article_list(xml_text)
                if names:
                    self.listArticles.clear()
                    for n in names:
                        self.listArticles.addItem(n)

            # 2) Probeer ALTIJD de fields te extraheren; lukt het → GUI vullen
            fields = parse_article_fields(xml_text)
            if fields:
                self.current_fields = fields
                self.populate_fields_view(fields)
        except Exception:
            # stil falen, raw blijft staan
            pass

# [END: on_received]
# [END: ManualTool]



# [FUNC: main]
def main():
    app = QtWidgets.QApplication(sys.argv)
    w = ManualTool()
    w.show()
    sys.exit(app.exec())

# [END: main]

# [SECTION: CLI / Entrypoint]
if __name__ == "__main__":
    main()
# [END: CLI / Entrypoint]
