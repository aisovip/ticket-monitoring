# -*- coding: utf-8 -*-
"""r325 去哪儿国际分支（B 级浏览器单路径，调研 report_qunar.md）。

实证基线：touchInterList 与国内 touchInnerList 同族（同 SPA/同
Bella/同 binfo 行结构），未登录=1999 硬拒，风控状态机 code 7/8/9
+bstatus 10004。离线可钉三件：

- 响应风控态机（Judge 源码实证的码表分流）；
- routes 行 → 统一元素 schema 映射（minPrice 含税口径 + 国际特有
  taxPrice/nakedPrice 拆分 + binfo2 整体到达）；
- 国际 URL 城市名三级回退（国内字典 → 国际城市级短名 → 裸码）。

网络面（浏览器握手/Bella/t1000 动态解码）无法离线钉，按 report
§7.3 生产登录态首采 dump 定谳后补映射（解析已全 .get 容错）。

运行：PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_intl_qunar.py
"""
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.qunar import QunarCrawler  # noqa: E402

_LOG = logging.getLogger("t_intl_qunar")
_QN = QunarCrawler({}, _LOG)


def _resp(data=None, code=0, bstatus=None):
    o = {"code": code, "ret": True}
    if bstatus is not None:
        o["bstatus"] = {"code": bstatus}
    if data is not None:
        o["data"] = data
    return json.dumps(o)


def _route_row(**over):
    row = {
        "code": "NH960",
        "minPrice": 2380, "nakedPrice": 1860, "taxPrice": 520,
        "transCity": "",
        "cabinDesc": "经济舱",
        "fewTicket": "",
        "binfo": {"depTime": "09:30", "arrTime": "14:00",
                  "depDate": "2026-11-16", "arrDate": "2026-11-16"},
    }
    row.update(over)
    return row


# ---- 风控态机 ----

def test_risk_state_machine():
    # Judge 状态机码表（report §6.1 源码实证）：只分流不绕过
    assert _QN._parse_intl_response(_resp(bstatus=1999))[1] == "login"
    assert _QN._parse_intl_response(_resp(code=8))[1] == "login"
    # 校准 R8 生产 profile 实测形态：bstatus 2008 与 code 8 同现
    assert _QN._parse_intl_response(_resp(bstatus=2008))[1] == "login"
    assert _QN._parse_intl_response(_resp(code=7))[1] == "slider"
    assert _QN._parse_intl_response(_resp(code=9))[1] == "refresh"
    assert _QN._parse_intl_response(_resp(bstatus=10004))[1] == "captcha"
    assert _QN._parse_intl_response("not-json")[1] == ""


# ---- 行映射 ----

def test_intl_row_mapping_minprice_included_tax():
    rows, risk = _QN._parse_intl_response(
        _resp({"routes": [_route_row()]}))
    assert risk == "" and len(rows) == 1
    r = rows[0]
    assert r["price"] == 2380            # minPrice=含税口径
    assert r["tax"] == 520               # 国际特有拆分透传
    assert r["nakedPrice"] == 1860
    assert r["cabin"] == "经济舱"
    assert r["airlineCode"] == "NH"
    assert r["depTime"] == "09:30" and r["arrTime"] == "14:00"
    assert "transCity" not in r          # 直飞行不落中转键


def test_intl_transfer_arrival_from_binfo2():
    rows, _ = _QN._parse_intl_response(_resp({"routes": [_route_row(
        code="MU523/NH960", transCity="东京",
        binfo={"depTime": "09:30", "arrTime": "12:10",
               "depDate": "2026-11-16", "arrDate": "2026-11-16"},
        binfo2={"arrTime": "16:40", "arrDate": "2026-11-16"})]}))
    # 中转整体到达=binfo2（report §4 渲染实证），出发仍取首段
    assert rows[0]["arrTime"] == "16:40"
    assert rows[0]["depTime"] == "09:30"
    assert rows[0]["transCity"] == "东京"


def test_intl_wide_band_and_garbage():
    # 商务舱 >5 万国际合法；垃圾价剔
    rows, _ = _QN._parse_intl_response(
        _resp({"routes": [_route_row(minPrice=60000)]}))
    assert rows[0]["price"] == 60000
    rows2, _ = _QN._parse_intl_response(
        _resp({"routes": [_route_row(minPrice=99)]}))
    assert rows2 == []
    # 缺时刻行剔（宁缺勿错）
    rows3, _ = _QN._parse_intl_response(_resp({"routes": [_route_row(
        binfo={"depTime": "09:30", "arrTime": "",
               "depDate": "2026-11-16", "arrDate": "2026-11-16"})]}))
    assert rows3 == []


# ---- R40 真报文行形态（登录态 dump 普查 60 行实测账）----

def _intl_row_real(**over):
    """touchInterList 登录态真报文行（R40 census 60/60 实测）：
    code=list、价格四键字符串、fewTicketStr 键、transCity 只在
    binfo、binfo.name=航司中文名列表、机场/航站楼/时长在 binfo。"""
    row = {
        "type": 0,
        "code": ["GK36|PVG-NRT|2026-11-16|09:35"],
        "minPrice": "1499", "nakedPrice": "1099", "taxPrice": "400",
        "totalPrice": "1499",
        "flightCode": "GK36|PVG-NRT|2026-11-16|09:35@sess",
        "flightKey": "GK36|PVG-NRT|2026-11-16|09:35@sess",
        "fewTicketStr": "",
        "cabinDesc": "经济舱",
        "extparams": "{}",
        "reducePriceDesc": "", "ticketInsufficient": "",
        "binfo": {"name": ["捷星日本航空"], "airCode": ["GK"],
                  "depCity": "上海", "depAirport": "浦东",
                  "depTerminal": "T2", "depTime": "09:35",
                  "depDate": "2026-11-16",
                  "arrCity": "东京", "arrAirport": "成田",
                  "arrTerminal": "T3", "arrTime": "13:30",
                  "arrDate": "2026-11-16",
                  "stops": 0, "totalDuration": "3小时55分",
                  "codeShare": "0", "crossDayDesc": "",
                  "transNotice": ""},
    }
    row.update(over)
    return row


def test_r40_real_payload_flights_key_and_string_prices():
    """R40 分账 P0：真报文航班数组键名是 flights（无 routes 键），
    容器取错则 JSON 路径恒 0 行（生产登录后 21:48/21:51 两连败
    实锤）。价格四键全为字符串数字。"""
    rows, risk = _QN._parse_intl_response(
        _resp({"flights": [_intl_row_real()]}))
    assert risk == "" and len(rows) == 1
    r = rows[0]
    assert r["price"] == 1499.0          # 字符串 minPrice
    assert r["tax"] == 400.0             # 字符串 taxPrice
    assert r["nakedPrice"] == 1099.0
    assert r["code"] == "GK36"           # code 列表归一取首段航班号
    assert r["airlineCode"] == "GK"
    # mixFlightName 缺席 → binfo.name 航司中文名（非裸 code 串）
    assert r["name"] == "捷星日本航空"
    # R42 信息量对齐：时长/机场名对落地；codeShare "0"/crossDay 空
    # 串不落键（卫生律）
    assert r["totalDuration"] == "3小时55分"
    assert r["depAirport"] == "浦东" and r["arrAirport"] == "成田"
    assert "codeShare" not in r and "crossDayDesc" not in r
    # 旧 routes 键形态保持兼容（存量钉不改写）
    rows2, _ = _QN._parse_intl_response(
        _resp({"routes": [_route_row()]}))
    assert len(rows2) == 1


def test_r40_transcity_in_binfo_and_fewticketstr():
    """R40：中转城市在 binfo.transCity（37/60 行），行级键不存在；
    fewTicketStr 为真键名（行级 fewTicket 永缺席）。"""
    rows, _ = _QN._parse_intl_response(_resp({"flights": [
        _intl_row_real(
            code=["9C8515|PVG-NRT|2026-11-16|08:20",
                  "MM1033|NRT-CTS|2026-11-16|13:00"],
            binfo={"name": ["春秋航空", "乐桃航空"],
                   "airCode": ["9C", "MM"],
                   "depCity": "上海", "depAirport": "浦东",
                   "depTerminal": "T2", "depTime": "08:20",
                   "depDate": "2026-11-16",
                   "arrCity": "札幌", "arrAirport": "新千岁",
                   "arrTerminal": "T2", "arrTime": "18:05",
                   "arrDate": "2026-11-16",
                   "stops": 1, "totalDuration": "9小时45分",
                   "codeShare": "0", "crossDayDesc": "",
                   "transNotice": "", "transCity": "东京"},
            fewTicketStr="余5张")]}))
    assert rows[0]["transCity"] == "东京"
    assert rows[0]["code"] == "9C8515/MM1033"
    assert rows[0]["name"] == "春秋航空/乐桃航空"   # 多段航司名 / 连接
    assert rows[0]["fewTicket"] == "余5张"
    assert rows[0]["arrTime"] == "18:05"   # 无 binfo2 回落 binfo 整体到达
    # R42 维度在中转行同样落地；crossDayDesc 空串不落键
    assert rows[0]["totalDuration"] == "9小时45分"
    assert rows[0]["depAirport"] == "浦东" and rows[0]["arrAirport"] == "新千岁"
    assert "crossDayDesc" not in rows[0]
    # codeShare 非 "0" 形态落旗标
    rows3, _ = _QN._parse_intl_response(_resp({"flights": [
        _intl_row_real(binfo={**_intl_row_real()["binfo"],
                              "codeShare": "1"})]}))
    assert rows3[0]["codeShare"] == "1"
    # binfo.name 重复航司去重（同司两段不重复展示）
    rows2, _ = _QN._parse_intl_response(_resp({"flights": [
        _intl_row_real(
            binfo={**_intl_row_real()["binfo"],
                   "name": ["春秋航空", "春秋航空"]})]}))
    assert rows2[0]["name"] == "春秋航空"


# ---- 城市名回退 ----

def test_intl_city_name_fallback_chain():
    # 国内码走存量字典（中文名）
    assert _QN._intl_city_name("SHA") == "上海"
    # 国际码走城市级短名（搜索参数是中文城市名，report §3）
    assert _QN._intl_city_name("NRT") == "东京"
    assert _QN._intl_city_name("LHR") == "伦敦"
    # 短名表外回退展示名再回退裸码（宁缺勿错不猜）
    assert _QN._intl_city_name("ZZZ") == "ZZZ"


# ---- r326 补采：多段行 transCity 断供链式推导 ----
#    （channel_ctrip_qunar.md §2.1：495 行冻结语料 429 行多段、
#    74 行多段 transCity 断供以「直飞」身份污染直飞池——code[] 段链
#    FNO|FROM-TO|DATE 链式推导，渠道真值在场即定谳不覆盖）

def _seg_row(code_list, **over):
    return _route_row(
        code=code_list,
        binfo={"depTime": "08:20", "arrTime": "12:10",
               "depDate": "2026-11-16", "arrDate": "2026-11-17"},
        **over)


def test_intl_transcity_derive_from_code_chain():
    # 两段一转（dump AY88|PVG-HEL + AY1571|HEL-CDG 实证形态）：
    # 转点=段间衔接港，城市名走 city_name_of 统一链
    rows, _ = _QN._parse_intl_response(
        _resp({"routes": [_seg_row(
            ["AY88|PVG-HEL|2026-11-16", "AY1571|HEL-CDG|2026-11-17"])]}))
    assert rows[0]["transCity"] == "赫尔辛基"


def test_intl_transcity_derive_multiseg_and_stop_skip():
    # 3 段两转（dump MU5075|PVG-HAN + CA884|HAN-PEK + CA933|PEK-CDG
    # '2转' 实证形态）：两转点全推导按序 / 连接；同号续段=经停不换机
    # 不入转点（宁缺勿错）
    rows, _ = _QN._parse_intl_response(_resp({"routes": [_seg_row(
        ["MU5075|PVG-HAN|2026-11-16", "CA884|HAN-PEK|2026-11-17",
         "CA933|PEK-CDG|2026-11-17"])]}))
    # PEK 无城市映射（CITY=城市码域、INTL 177 无机场级）——裸码兜底，
    # 真实 dump 样本形态如实钉
    assert rows[0]["transCity"] == "河内/PEK"
    stop, _ = _QN._parse_intl_response(_resp({"routes": [_seg_row(
        ["MU5075|PVG-HAN|2026-11-16", "MU5075|HAN-CDG|2026-11-17"])]}))
    assert "transCity" not in stop[0]


def test_intl_transcity_channel_truth_wins_and_raw_code_fallback():
    # 渠道真值在场即定谳（推导不覆盖）；映射缺城落裸码（真值仍优于
    # 误判直飞——断供伤害面=锚池污染+读者误读，裸码两者皆解）
    rows, _ = _QN._parse_intl_response(_resp({"routes": [_seg_row(
        ["GF125|PVG-BAH|2026-11-16", "PR3312|BAH-DXB|2026-11-17"],
        transCity="")]}))
    assert rows[0]["transCity"] == "BAH"
    rows2, _ = _QN._parse_intl_response(_resp({"routes": [_seg_row(
        ["AY88|PVG-HEL|2026-11-16", "AY1571|HEL-CDG|2026-11-17"],
        transCity="赫尔辛基")]}))
    assert rows2[0]["transCity"] == "赫尔辛基"


def test_intl_transcity_derive_degenerate_shapes():
    # 段链元素缺 FROM-TO 段/链不衔接（TO≠下段 FROM）不落转点
    rows, _ = _QN._parse_intl_response(_resp({"routes": [_seg_row(
        ["AY88", "AY1571|HEL-CDG|2026-11-17"])]}))
    assert "transCity" not in rows[0]
    rows2, _ = _QN._parse_intl_response(_resp({"routes": [_seg_row(
        ["AY88|PVG-HEL|2026-11-16", "AY1571|ARN-CDG|2026-11-17"])]}))
    assert "transCity" not in rows2[0]
