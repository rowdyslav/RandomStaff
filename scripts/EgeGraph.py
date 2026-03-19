from __future__ import annotations

from dataclasses import dataclass
from re import fullmatch

import altair as alt
import httpx
import pandas as pd
import streamlit as st
from selectolax.parser import HTMLParser

SOURCE_NAME = "4ege"
SOURCE_URL = "https://4ege.ru/novosti-ege/4023-shkala-perevoda-ballov-ege.html"
SOURCE_DATE = "7 мая 2025. На странице указано: «Информация актуальна для выпускников 2026»."
SOURCE_NOTE = (
    "Приложение сначала пытается получить живые данные с 4ege и распарсить их через Selectolax. "
    "Если сайт недоступен, используется резервный снимок этой же шкалы 2026."
)

SUBJECTS: tuple[str, ...] = (
    "Математика (профиль)",
    "Русский язык",
    "Биология",
    "История",
    "Информатика",
    "Обществознание",
    "Химия",
    "Физика",
    "Иностранные языки",
    "Китайский язык",
    "География",
    "Литература",
)

FALLBACK_SCALES: dict[str, list[int]] = {
    "Математика (профиль)": [0, 6, 11, 17, 22, 27, 34, 40, 46, 52, 58, 64, 70, 72, 74, 76, 78, 80, 82, 84, 86, 88, 90, 92, 94, 95, 96, 97, 98, 99, 100, 100, 100],
    "Русский язык": [0, 3, 5, 8, 10, 12, 15, 17, 20, 22, 24, 27, 29, 32, 34, 36, 37, 39, 40, 42, 43, 45, 46, 48, 49, 51, 52, 54, 55, 57, 58, 60, 61, 63, 64, 66, 67, 69, 70, 72, 73, 75, 78, 81, 83, 86, 89, 91, 94, 97, 100],
    "Биология": [0, 3, 5, 7, 10, 12, 14, 17, 19, 21, 24, 26, 28, 31, 33, 36, 38, 40, 41, 43, 45, 46, 48, 50, 51, 53, 55, 56, 58, 60, 61, 63, 65, 66, 68, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 83, 85, 86, 88, 90, 91, 93, 95, 96, 98, 100],
    "История": [0, 4, 8, 12, 16, 20, 24, 28, 32, 34, 36, 38, 40, 42, 44, 45, 47, 49, 51, 53, 55, 57, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 82, 84, 87, 89, 91, 93, 95, 97, 100],
    "Информатика": [0, 7, 14, 20, 27, 34, 40, 43, 46, 48, 51, 54, 56, 59, 62, 64, 67, 70, 72, 75, 78, 80, 83, 85, 88, 90, 93, 95, 98, 100],
    "Обществознание": [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 45, 47, 48, 49, 51, 52, 53, 55, 56, 57, 59, 60, 62, 63, 64, 66, 67, 68, 70, 71, 72, 73, 75, 77, 79, 81, 83, 85, 86, 88, 90, 92, 94, 96, 98, 100],
    "Химия": [0, 4, 7, 10, 14, 17, 20, 23, 27, 30, 33, 36, 38, 39, 40, 42, 43, 44, 46, 47, 48, 49, 51, 52, 53, 55, 56, 57, 58, 60, 61, 62, 64, 65, 66, 68, 69, 70, 71, 73, 74, 75, 77, 78, 79, 80, 82, 84, 86, 88, 90, 91, 93, 95, 97, 99, 100],
    "Физика": [0, 5, 9, 14, 18, 23, 27, 32, 36, 39, 41, 43, 44, 46, 48, 49, 51, 53, 54, 56, 58, 59, 61, 62, 64, 65, 67, 68, 70, 71, 73, 74, 76, 77, 79, 80, 82, 84, 86, 88, 90, 92, 94, 96, 98, 100],
    "Иностранные языки": [0, 2, 3, 4, 5, 7, 8, 9, 10, 11, 13, 14, 15, 16, 18, 19, 20, 21, 22, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 84, 86, 88, 90, 92, 94, 96, 98, 100],
    "Китайский язык": [0, 2, 3, 4, 5, 7, 8, 9, 10, 12, 13, 14, 15, 17, 18, 19, 20, 22, 23, 24, 25, 27, 28, 29, 30, 32, 33, 34, 35, 37, 38, 39, 40, 42, 43, 44, 45, 47, 48, 49, 50, 52, 53, 54, 55, 57, 58, 59, 60, 62, 63, 64, 65, 67, 68, 69, 70, 72, 73, 74, 75, 77, 78, 79, 80, 82, 83, 84, 85, 87, 88, 89, 90, 92, 93, 94, 95, 97, 98, 99, 100],
    "География": [0, 5, 9, 13, 17, 21, 25, 29, 33, 37, 39, 40, 41, 43, 44, 45, 47, 48, 49, 51, 53, 54, 55, 57, 58, 59, 61, 62, 63, 65, 66, 68, 72, 77, 81, 86, 90, 95, 100],
    "Литература": [0, 3, 5, 8, 10, 13, 15, 18, 20, 23, 25, 28, 30, 32, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 63, 68, 73, 78, 84, 89, 94, 100],
}


@dataclass(frozen=True)
class SubjectScale:
    name: str
    scores: list[int]
    source_name: str
    source_url: str
    source_date: str
    note: str

    @property
    def max_primary(self) -> int:
        return len(self.scores) - 1


def make_scale(name: str, scores: list[int], *, note: str) -> SubjectScale:
    return SubjectScale(
        name=name,
        scores=scores,
        source_name=SOURCE_NAME,
        source_url=SOURCE_URL,
        source_date=SOURCE_DATE,
        note=note,
    )


def normalize_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.replace("\xa0", " ").splitlines():
        line = " ".join(raw_line.split()).strip()
        if line:
            lines.append(line)
    return lines


def extract_text_from_html(html: str) -> list[str]:
    parser = HTMLParser(html)
    body = parser.body
    if body is None:
        raise ValueError("HTML без body, парсинг невозможен.")
    return normalize_lines(body.text(separator="\n"))


def find_header_index(lines: list[str], header: str, start_index: int = 0) -> int:
    for index, line in enumerate(lines[start_index:], start_index):
        if line == header:
            return index
    raise ValueError(f"Не найден заголовок таблицы: {header}")


def source_header(subject_name: str) -> str:
    if subject_name == "Математика (профиль)":
        return "Математика. Профильный уровень"
    return subject_name


def parse_subject_scores(
    lines: list[str],
    header: str,
    all_headers: set[str],
    section_start: int,
) -> list[int]:
    start_index = find_header_index(lines, header, start_index=section_start)
    pairs: list[tuple[int, int]] = []
    index = start_index + 1
    last_primary = -1

    while index < len(lines):
        line = lines[index]
        if line in all_headers and pairs:
            break

        if fullmatch(r"\d+", line) and index + 1 < len(lines):
            next_line = lines[index + 1]
            if fullmatch(r"\d+", next_line):
                primary = int(line)
                test_score = int(next_line)
                if primary <= last_primary:
                    break
                pairs.append((primary, test_score))
                last_primary = primary
                index += 2
                continue

        index += 1

    if not pairs:
        raise ValueError(f"У предмета '{header}' не нашлось числовой таблицы.")

    max_primary = pairs[-1][0]
    scores = [0] * (max_primary + 1)
    for primary, test_score in pairs:
        scores[primary] = test_score
    return scores


def parse_live_scales(html: str) -> dict[str, list[int]]:
    lines = extract_text_from_html(html)
    section_start = find_header_index(lines, "Соответствие первичных и тестовых баллов")
    headers = {source_header(subject_name) for subject_name in SUBJECTS}
    return {
        subject_name: parse_subject_scores(
            lines,
            source_header(subject_name),
            headers,
            section_start,
        )
        for subject_name in SUBJECTS
    }


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def load_subject_scales() -> tuple[dict[str, SubjectScale], bool, str]:
    note = SOURCE_NOTE
    try:
        response = httpx.get(
            SOURCE_URL,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        parsed = parse_live_scales(response.text)
        scales = {
            name: make_scale(name, scores, note=note + " Сейчас используются живые данные со страницы.")
            for name, scores in parsed.items()
        }
        return scales, False, "Живые данные загружены с 4ege."
    except Exception as error:
        scales = {
            name: make_scale(name, scores, note=note + " Сейчас используется локальный резервный снимок.")
            for name, scores in FALLBACK_SCALES.items()
        }
        return scales, True, f"Не удалось обновить данные онлайн: {error}"


def build_dataframe(scale: SubjectScale) -> pd.DataFrame:
    fair_step = 100 / scale.max_primary
    rows: list[dict[str, float | int | str]] = []

    for primary, test_score in enumerate(scale.scores):
        uniform = primary * fair_step
        previous_score = scale.scores[primary - 1] if primary else 0
        gain = test_score - previous_score if primary else 0
        gain_delta = gain - fair_step if primary else 0.0
        diff = test_score - uniform

        if abs(diff) <= 1.5:
            balance = "почти честно"
        elif diff > 0:
            balance = "в пользу ученика"
        else:
            balance = "против ученика"

        rows.append(
            {
                "Первичный балл": primary,
                "Тестовый балл": test_score,
                "Равномерная шкала": uniform,
                "Отклонение": diff,
                "Прирост за этот балл": gain,
                "Отклонение прироста": gain_delta,
                "Статус": balance,
            }
        )

    return pd.DataFrame(rows)


def build_curve_chart(df: pd.DataFrame, selected_primary: int) -> alt.Chart:
    selected = pd.DataFrame([df.iloc[selected_primary]])
    source = df.melt(
        id_vars=["Первичный балл"],
        value_vars=["Тестовый балл", "Равномерная шкала"],
        var_name="Линия",
        value_name="Значение",
    )

    line = (
        alt.Chart(source)
        .mark_line(point=False, strokeWidth=3)
        .encode(
            x=alt.X("Первичный балл:Q", title="Первичный балл"),
            y=alt.Y("Значение:Q", title="Тестовый балл", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color(
                "Линия:N",
                scale=alt.Scale(
                    domain=["Тестовый балл", "Равномерная шкала"],
                    range=["#1565C0", "#B0BEC5"],
                ),
                legend=alt.Legend(title=None),
            ),
        )
    )

    points = (
        alt.Chart(df)
        .mark_circle(size=70)
        .encode(
            x="Первичный балл:Q",
            y="Тестовый балл:Q",
            color=alt.Color(
                "Статус:N",
                scale=alt.Scale(
                    domain=["в пользу ученика", "почти честно", "против ученика"],
                    range=["#2E7D32", "#F9A825", "#C62828"],
                ),
                legend=alt.Legend(title="Отклонение"),
            ),
            tooltip=[
                "Первичный балл:Q",
                "Тестовый балл:Q",
                alt.Tooltip("Равномерная шкала:Q", format=".1f"),
                alt.Tooltip("Отклонение:Q", format="+.1f"),
                alt.Tooltip("Прирост за этот балл:Q", format="+.1f"),
            ],
        )
    )

    marker = (
        alt.Chart(selected)
        .mark_rule(color="#111827", strokeDash=[6, 6], strokeWidth=2)
        .encode(x="Первичный балл:Q")
    )

    return (line + points + marker).properties(height=420)


def build_gain_chart(df: pd.DataFrame, fair_step: float, selected_primary: int) -> alt.Chart:
    gains = df[df["Первичный балл"] > 0].copy()
    selected = gains[gains["Первичный балл"] == selected_primary]
    gains["Интервал"] = gains["Первичный балл"].apply(lambda value: f"{value - 1}->{value}")

    bars = (
        alt.Chart(gains)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("Первичный балл:O", title="Баллы, которые ты добираешь"),
            y=alt.Y("Прирост за этот балл:Q", title="Сколько тестовых дает следующий первичный"),
            color=alt.Color(
                "Отклонение прироста:Q",
                scale=alt.Scale(domainMid=0, range=["#C62828", "#FDD835", "#2E7D32"]),
                legend=alt.Legend(title="Относительно честной шкалы"),
            ),
            tooltip=[
                alt.Tooltip("Интервал:N", title="Переход"),
                alt.Tooltip("Прирост за этот балл:Q", format="+.1f"),
                alt.Tooltip("Отклонение прироста:Q", format="+.2f"),
            ],
        )
    )

    rule = alt.Chart(pd.DataFrame({"fair": [fair_step]})).mark_rule(
        color="#455A64",
        strokeDash=[4, 4],
        strokeWidth=2,
    ).encode(y="fair:Q")

    marker = (
        alt.Chart(selected)
        .mark_bar(color="#111827", opacity=0.15)
        .encode(x="Первичный балл:O")
    )

    return (bars + rule + marker).properties(height=360)


def top_intervals(df: pd.DataFrame, ascending: bool) -> pd.DataFrame:
    gains = df[df["Первичный балл"] > 0].copy()
    gains["Переход"] = gains["Первичный балл"].apply(lambda value: f"{value - 1} -> {value}")
    result = gains.sort_values("Прирост за этот балл", ascending=ascending).head(5)
    return result[["Переход", "Прирост за этот балл", "Тестовый балл", "Отклонение"]]


def fair_zone(df: pd.DataFrame) -> tuple[int, int]:
    fair_points = df[df["Статус"] == "почти честно"]["Первичный балл"].tolist()
    if not fair_points:
        return (0, 0)

    best_start = fair_points[0]
    best_end = fair_points[0]
    start = fair_points[0]
    previous = fair_points[0]

    for point in fair_points[1:]:
        if point == previous + 1:
            previous = point
            if previous - start > best_end - best_start:
                best_start, best_end = start, previous
            continue
        start = point
        previous = point

    return (best_start, best_end)


def render_summary(scale: SubjectScale, df: pd.DataFrame, selected_primary: int) -> None:
    fair_step = 100 / scale.max_primary
    row = df.iloc[selected_primary]
    best_gain = int(df["Прирост за этот балл"].idxmax())
    worst_gain = int(df[df["Первичный балл"] > 0]["Прирост за этот балл"].idxmin())
    zone_start, zone_end = fair_zone(df)

    metric_cols = st.columns(4)
    metric_cols[0].metric(
        "Выбранный балл",
        f"{selected_primary} -> {int(row['Тестовый балл'])}",
        f"{row['Отклонение']:+.1f} к честной шкале",
    )
    metric_cols[1].metric(
        "Самый ценный шаг",
        f"{best_gain - 1} -> {best_gain}",
        f"+{int(df.iloc[best_gain]['Прирост за этот балл'])} тестовых",
    )
    metric_cols[2].metric(
        "Самый слабый шаг",
        f"{worst_gain - 1} -> {worst_gain}",
        f"+{int(df.iloc[worst_gain]['Прирост за этот балл'])} тестовых",
    )
    metric_cols[3].metric(
        "Условно честный участок",
        f"{zone_start}..{zone_end}",
        f"шаг честной шкалы: {fair_step:.2f}",
    )


def main() -> None:
    st.set_page_config(page_title="ЕГЭ: ценность первичных баллов", page_icon="📈", layout="wide")

    st.title("ЕГЭ: где первичные баллы действительно самые ценные")
    st.write(
        "Приложение сравнивает реальную шкалу перевода с математически равномерной. "
        "Так видно, где следующий первичный балл дает повышенную отдачу, а где шкала начинает забирать выгоду."
    )

    if st.sidebar.button("Обновить данные сейчас", width="stretch"):
        load_subject_scales.clear()

    scales, using_fallback, status_message = load_subject_scales()

    st.sidebar.header("Параметры")
    subject_name = st.sidebar.selectbox("Предмет", list(scales))
    scale = scales[subject_name]
    df = build_dataframe(scale)

    selected_primary = st.sidebar.slider(
        "Разобрать конкретный первичный балл",
        min_value=0,
        max_value=scale.max_primary,
        value=min(scale.max_primary, int(scale.max_primary * 0.75)),
    )

    st.sidebar.markdown("### Источник данных")
    st.sidebar.markdown(f"[{scale.source_name}]({scale.source_url})")
    st.sidebar.caption(scale.source_date)
    st.sidebar.caption(scale.note)
    st.sidebar.info(
        "Базовая математика не включена: там официально пятибалльная шкала, "
        "а не перевод в стобалльный тестовый результат."
    )

    if using_fallback:
        st.warning(status_message)
    else:
        st.success(status_message)

    render_summary(scale, df, selected_primary)

    fair_step = 100 / scale.max_primary
    chart_cols = st.columns([1.35, 1])
    with chart_cols[0]:
        st.subheader("Реальная шкала против честной линейной")
        st.altair_chart(build_curve_chart(df, selected_primary), width="stretch")
    with chart_cols[1]:
        row = df.iloc[selected_primary]
        st.subheader("Разбор выбранной точки")
        st.markdown(
            f"""
            **Предмет:** {scale.name}

            **Первичный балл:** {selected_primary} из {scale.max_primary}

            **Реальный тестовый:** {int(row["Тестовый балл"])}

            **Честная линейная шкала:** {row["Равномерная шкала"]:.1f}

            **Отклонение:** {row["Отклонение"]:+.1f}

            **Цена именно этого шага:** {row["Прирост за этот балл"]:+.1f} тестовых
            Честная цена шага: {fair_step:.2f}
            """
        )

        if row["Отклонение"] > 1.5:
            st.success("Этот результат выше честной шкалы: перевод пока работает в пользу ученика.")
        elif row["Отклонение"] < -1.5:
            st.error("Этот результат ниже честной шкалы: шкала уже заметно съедает выгоду.")
        else:
            st.warning("Эта зона близка к математически честной.")

    st.subheader("Ценность каждого следующего первичного балла")
    st.altair_chart(build_gain_chart(df, fair_step, selected_primary), width="stretch")

    table_cols = st.columns(2)
    with table_cols[0]:
        st.subheader("Самые выгодные переходы")
        st.dataframe(top_intervals(df, ascending=False), width="stretch", hide_index=True)
    with table_cols[1]:
        st.subheader("Самые слабые переходы")
        st.dataframe(top_intervals(df, ascending=True), width="stretch", hide_index=True)

    with st.expander("Полная таблица перевода"):
        st.dataframe(
            df[
                [
                    "Первичный балл",
                    "Тестовый балл",
                    "Равномерная шкала",
                    "Отклонение",
                    "Прирост за этот балл",
                    "Статус",
                ]
            ],
            width="stretch",
            hide_index=True,
        )


if __name__ == "__main__":
    main()
