import re
from pathlib import Path

import pandas as pd
import streamlit as st



# ============================================================
# PAGE CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="Inverter Loading Ratio Calculation",
    page_icon="🔌",
    layout="wide"
)


# ============================================================
# SESSION STATE
# ============================================================
if "north_row_count" not in st.session_state:
    st.session_state.north_row_count = 1

if "south_row_count" not in st.session_state:
    st.session_state.south_row_count = 1


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def parse_string_quantities(text):
    """
    Accepts only positive integer quantities separated by spaces or line breaks.

    Example:
    20 20 20 16 16
    """
    cleaned = text.strip()

    if not cleaned:
        raise ValueError("String quantities cannot be blank.")

    if "," in cleaned:
        raise ValueError(
            "Use spaces between string quantities. Commas are not allowed."
        )

    if not re.fullmatch(r"\d+(\s+\d+)*", cleaned):
        raise ValueError(
            "String quantities must contain only positive integers separated by spaces."
        )

    values = [int(value) for value in cleaned.split()]

    if any(value <= 0 for value in values):
        raise ValueError("All string quantities must be greater than zero.")

    return values


def parse_lbd_row(text):
    """
    Parses LBD rows.

    Accepted examples:
    1 2 3 4 5
    11-15
    1 2 10-14 20

    Supports hyphen, en dash, and em dash.
    """
    cleaned = text.strip()

    if not cleaned:
        return []

    cleaned = re.sub(r"\s*[-–—]\s*", "-", cleaned)
    tokens = cleaned.split()

    lbd_numbers = []

    for token in tokens:
        match = re.fullmatch(r"(\d+)(?:-(\d+))?", token)

        if not match:
            raise ValueError(
                f"Invalid LBD entry '{token}'. Use values such as 1 2 3 or 11-15."
            )

        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else start

        if start <= 0 or end <= 0:
            raise ValueError("LBD numbers must be greater than zero.")

        if end < start:
            raise ValueError(
                f"Invalid range '{token}'. The final number must be greater than or equal to the first."
            )

        lbd_numbers.extend(range(start, end + 1))

    return lbd_numbers


def lbd_name(number):
    """Returns LBD01, LBD02 ... LBD100, etc."""
    return f"LBD{number:02d}"


def build_lbd_metadata(
    string_quantities,
    north_rows,
    south_rows,
    physical_layout_enabled
):
    """
    Creates the LBD data structure.

    North:
    - Last entered North row is closest to the skid.
    - Example with 3 rows:
      North Row 1 -> distance 3
      North Row 2 -> distance 2
      North Row 3 -> distance 1

    South:
    - First entered South row is closest to the skid.
    - Example with 3 rows:
      South Row 1 -> distance 1
      South Row 2 -> distance 2
      South Row 3 -> distance 3
    """
    total_lbds = len(string_quantities)

    lbd_data = []

    if not physical_layout_enabled:
        for index, strings in enumerate(string_quantities, start=1):
            lbd_data.append({
                "lbd_number": index,
                "lbd": lbd_name(index),
                "strings": strings,
                "reference_side": "Unrestricted",
                "reference_row": None,
                "distance_to_skid": 0
            })

        return lbd_data

    side_mapping = {}

    # North rows:
    # Last row added is closest to the skid.
    north_total_rows = len(north_rows)

    for row_index, row_lbd_numbers in enumerate(north_rows, start=1):
        distance_to_skid = north_total_rows - row_index + 1

        for lbd_number in row_lbd_numbers:
            if lbd_number in side_mapping:
                raise ValueError(
                    f"{lbd_name(lbd_number)} was entered more than once."
                )

            side_mapping[lbd_number] = {
                "reference_side": "North",
                "reference_row": row_index,
                "distance_to_skid": distance_to_skid
            }

    # South rows:
    # First row added is closest to the skid.
    for row_index, row_lbd_numbers in enumerate(south_rows, start=1):
        distance_to_skid = row_index

        for lbd_number in row_lbd_numbers:
            if lbd_number in side_mapping:
                raise ValueError(
                    f"{lbd_name(lbd_number)} was entered more than once."
                )

            side_mapping[lbd_number] = {
                "reference_side": "South",
                "reference_row": row_index,
                "distance_to_skid": distance_to_skid
            }

    invalid_lbds = [
        number for number in side_mapping
        if number < 1 or number > total_lbds
    ]

    if invalid_lbds:
        invalid_names = ", ".join(lbd_name(number) for number in invalid_lbds)
        raise ValueError(
            f"The following LBDs are outside the available string quantity list: "
            f"{invalid_names}"
        )

    expected_lbds = set(range(1, total_lbds + 1))
    assigned_lbds = set(side_mapping.keys())

    missing_lbds = sorted(expected_lbds - assigned_lbds)

    if missing_lbds:
        missing_names = ", ".join(lbd_name(number) for number in missing_lbds)
        raise ValueError(
            f"Every LBD must be assigned to North or South. Missing: {missing_names}"
        )

    for index, strings in enumerate(string_quantities, start=1):
        location = side_mapping[index]

        lbd_data.append({
            "lbd_number": index,
            "lbd": lbd_name(index),
            "strings": strings,
            "reference_side": location["reference_side"],
            "reference_row": location["reference_row"],
            "distance_to_skid": location["distance_to_skid"]
        })

    return lbd_data


def build_inverters(number_north, number_south):
    """
    Inverter numbering follows the requested TMEIC skid convention:

    South inverters first:
    Inv 1, Inv 2, Inv 3...

    North inverters continue afterward:
    Inv 4, Inv 5...
    """
    inverters = []
    inverter_number = 1

    for _ in range(number_south):
        inverters.append({
            "name": f"Inv {inverter_number}",
            "side": "South"
        })
        inverter_number += 1

    for _ in range(number_north):
        inverters.append({
            "name": f"Inv {inverter_number}",
            "side": "North"
        })
        inverter_number += 1

    return inverters


def calculate_loads(lbd_data, assignment, inverter_count):
    """Calculates total strings assigned to each inverter."""
    loads = [0] * inverter_count

    for lbd_index, inverter_index in enumerate(assignment):
        loads[inverter_index] += lbd_data[lbd_index]["strings"]

    return loads


def calculate_objective(
    lbd_data,
    assignment,
    inverters,
    physical_layout_enabled
):
    """
    Optimization priority:

    1. Minimize the maximum difference from the average inverter loading.
    2. Minimize the total squared deviation from the average loading.
    3. Minimize total number of North/South crossings.
    4. Minimize crossing distance from the skid.

    Therefore, crossing circuits are only selected when they improve
    the electrical balance or are necessary to reach an equivalent
    electrical balance.
    """
    inverter_count = len(inverters)
    loads = calculate_loads(lbd_data, assignment, inverter_count)

    total_strings = sum(loads)
    target = total_strings / inverter_count

    deviations = [abs(load - target) for load in loads]
    max_deviation = max(deviations)
    squared_deviation = sum((load - target) ** 2 for load in loads)

    if not physical_layout_enabled:
        return (
            round(max_deviation, 8),
            round(squared_deviation, 8)
        )

    crossing_count = 0
    crossing_distance = 0

    for lbd_index, inverter_index in enumerate(assignment):
        lbd = lbd_data[lbd_index]
        inverter = inverters[inverter_index]

        if lbd["reference_side"] != inverter["side"]:
            crossing_count += 1
            crossing_distance += lbd["distance_to_skid"]

    return (
        round(max_deviation, 8),
        round(squared_deviation, 8),
        crossing_count,
        crossing_distance
    )


def greedy_initial_assignment(
    lbd_data,
    inverters,
    physical_layout_enabled,
    respect_physical_side=True
):
    """
    Creates an initial LPT/greedy allocation.

    When respect_physical_side=True:
    LBDs are initially allocated only to inverters on their own side.

    When respect_physical_side=False:
    The allocation ignores North/South location and balances purely
    based on string quantities.
    """
    inverter_count = len(inverters)
    assignment = [-1] * len(lbd_data)
    loads = [0] * inverter_count

    # Larger blocks first.
    sorted_indices = sorted(
        range(len(lbd_data)),
        key=lambda i: (
            -lbd_data[i]["strings"],
            lbd_data[i]["distance_to_skid"]
        )
    )

    for lbd_index in sorted_indices:
        lbd = lbd_data[lbd_index]

        if physical_layout_enabled and respect_physical_side:
            candidate_inverters = [
                index
                for index, inverter in enumerate(inverters)
                if inverter["side"] == lbd["reference_side"]
            ]

            if not candidate_inverters:
                raise ValueError(
                    f"{lbd['lbd']} is on the {lbd['reference_side']} side, "
                    f"but there are no inverters configured on that side."
                )
        else:
            candidate_inverters = list(range(inverter_count))

        chosen_inverter = min(
            candidate_inverters,
            key=lambda inverter_index: (
                loads[inverter_index],
                inverter_index
            )
        )

        assignment[lbd_index] = chosen_inverter
        loads[chosen_inverter] += lbd["strings"]

    return assignment


def optimize_assignment(
    lbd_data,
    initial_assignment,
    inverters,
    physical_layout_enabled,
    max_iterations=250
):
    """
    Applies iterative improvement using:

    - Individual LBD moves
    - LBD swaps between inverter assignments

    This improves the initial greedy distribution while preserving
    the optimization priority defined in calculate_objective().
    """
    current_assignment = initial_assignment.copy()

    current_objective = calculate_objective(
        lbd_data,
        current_assignment,
        inverters,
        physical_layout_enabled
    )

    inverter_count = len(inverters)
    lbd_count = len(lbd_data)

    for _ in range(max_iterations):
        best_assignment = current_assignment
        best_objective = current_objective
        improvement_found = False

        # ----------------------------------------------------
        # INDIVIDUAL LBD MOVES
        # ----------------------------------------------------
        for lbd_index in range(lbd_count):
            current_inverter = current_assignment[lbd_index]

            for candidate_inverter in range(inverter_count):
                if candidate_inverter == current_inverter:
                    continue

                candidate_assignment = current_assignment.copy()
                candidate_assignment[lbd_index] = candidate_inverter

                candidate_objective = calculate_objective(
                    lbd_data,
                    candidate_assignment,
                    inverters,
                    physical_layout_enabled
                )

                if candidate_objective < best_objective:
                    best_assignment = candidate_assignment
                    best_objective = candidate_objective
                    improvement_found = True

        # ----------------------------------------------------
        # SWAPS BETWEEN TWO LBDS
        # ----------------------------------------------------
        for first_lbd in range(lbd_count):
            for second_lbd in range(first_lbd + 1, lbd_count):
                first_inverter = current_assignment[first_lbd]
                second_inverter = current_assignment[second_lbd]

                if first_inverter == second_inverter:
                    continue

                candidate_assignment = current_assignment.copy()
                candidate_assignment[first_lbd] = second_inverter
                candidate_assignment[second_lbd] = first_inverter

                candidate_objective = calculate_objective(
                    lbd_data,
                    candidate_assignment,
                    inverters,
                    physical_layout_enabled
                )

                if candidate_objective < best_objective:
                    best_assignment = candidate_assignment
                    best_objective = candidate_objective
                    improvement_found = True

        if not improvement_found:
            break

        current_assignment = best_assignment
        current_objective = best_objective

    return current_assignment, current_objective


def find_best_distribution(
    lbd_data,
    inverters,
    physical_layout_enabled
):
    """
    Runs more than one starting point and retains the best final result.

    Starting point 1:
    Physical-side-first allocation.

    Starting point 2:
    Pure mathematical/global allocation.

    The final result is selected using the same objective hierarchy.
    """
    candidate_assignments = []

    if physical_layout_enabled:
        candidate_assignments.append(
            greedy_initial_assignment(
                lbd_data,
                inverters,
                physical_layout_enabled=True,
                respect_physical_side=True
            )
        )

        candidate_assignments.append(
            greedy_initial_assignment(
                lbd_data,
                inverters,
                physical_layout_enabled=True,
                respect_physical_side=False
            )
        )
    else:
        candidate_assignments.append(
            greedy_initial_assignment(
                lbd_data,
                inverters,
                physical_layout_enabled=False,
                respect_physical_side=False
            )
        )

    best_assignment = None
    best_objective = None

    for initial_assignment in candidate_assignments:
        optimized_assignment, objective = optimize_assignment(
            lbd_data=lbd_data,
            initial_assignment=initial_assignment,
            inverters=inverters,
            physical_layout_enabled=physical_layout_enabled
        )

        if best_objective is None or objective < best_objective:
            best_assignment = optimized_assignment
            best_objective = objective

    return best_assignment, best_objective


def build_result_tables(
    lbd_data,
    assignment,
    inverters,
    modules_per_string,
    module_power_w,
    inverter_power_kva,
    physical_layout_enabled
):
    """Builds the inverter summary and LBD-level assignment tables."""
    inverter_count = len(inverters)
    loads = calculate_loads(lbd_data, assignment, inverter_count)

    summary_rows = []

    for inverter_index, inverter in enumerate(inverters):
        total_strings = loads[inverter_index]
        dc_power_kw = (
            total_strings
            * modules_per_string
            * module_power_w
            / 1000
        )

        ilr = (
            dc_power_kw / inverter_power_kva
            if inverter_power_kva > 0
            else 0
        )

        assigned_lbds = [
            lbd_data[lbd_index]["lbd"]
            for lbd_index, assigned_inverter in enumerate(assignment)
            if assigned_inverter == inverter_index
        ]

        summary_rows.append({
            "Inverter": inverter["name"],
            "Side": inverter["side"],
            "Total Strings": total_strings,
            "DC Power (kW)": round(dc_power_kw, 2),
            "ILR": round(ilr, 3),
            "Assigned LBDs": ", ".join(assigned_lbds)
        })

    assignment_rows = []

    for lbd_index, inverter_index in enumerate(assignment):
        lbd = lbd_data[lbd_index]
        inverter = inverters[inverter_index]

        is_crossing = (
            physical_layout_enabled
            and lbd["reference_side"] != inverter["side"]
        )

        if is_crossing:
            crossing_direction = (
                f"{lbd['reference_side']} → {inverter['side']}"
            )
        else:
            crossing_direction = ""

        assignment_rows.append({
            "LBD": lbd["lbd"],
            "Strings": lbd["strings"],
            "Reference Side": lbd["reference_side"],
            "Reference Row": (
                f"Row {lbd['reference_row']}"
                if lbd["reference_row"] is not None
                else ""
            ),
            "Distance to Skid": lbd["distance_to_skid"],
            "Assigned Inverter": inverter["name"],
            "Inverter Side": inverter["side"],
            "Crossing Required": "Yes" if is_crossing else "No",
            "Crossing Direction": crossing_direction
        })

    summary_df = pd.DataFrame(summary_rows)
    assignment_df = pd.DataFrame(assignment_rows)

    return summary_df, assignment_df


# ============================================================
# SIDEBAR INPUTS
# ============================================================
with st.sidebar:
    st.header("Input Parameters")

    string_input = st.text_area(
        "String quantities (space bar separated)",
        value="20 20 20 20 20 20 20 20 20 16 20 16 16",
        height=100,
        help=(
            "Each value corresponds sequentially to LBD01, LBD02, LBD03, etc. "
            "Example: 20 20 16 means LBD01 = 20 strings, "
            "LBD02 = 20 strings, and LBD03 = 16 strings."
        )
    )

    physical_layout_option = st.radio(
        "Skid physical layout",
        options=[
            "North / South aware",
            "No physical-side restriction"
        ],
        index=0,
        help=(
            "North / South aware prioritizes same-side assignments and "
            "minimizes circuit crossings. No physical-side restriction "
            "uses only mathematical load balancing."
        )
    )

    physical_layout_enabled = (
        physical_layout_option == "North / South aware"
    )

    st.markdown("---")
    st.subheader("Inverter Configuration")

    inverter_col_1, inverter_col_2 = st.columns(2)

    with inverter_col_1:
        number_inverters_north = st.number_input(
            "Number of inverters North",
            min_value=0,
            step=1,
            value=2
        )

    with inverter_col_2:
        number_inverters_south = st.number_input(
            "Number of inverters South",
            min_value=0,
            step=1,
            value=3
        )

    inverter_power_kva = st.number_input(
        "Inverter AC power (kVA)",
        min_value=1.0,
        step=10.0,
        value=1100.0
    )

    modules_per_string = st.number_input(
        "Modules per string",
        min_value=1,
        step=1,
        value=27
    )

    module_power_w = st.number_input(
        "Module power (W)",
        min_value=1.0,
        step=5.0,
        value=625.0
    )

    if physical_layout_enabled:
        st.markdown("---")
        st.subheader("North LBD Rows")

        st.caption(
            "North priority: the last row added is closest to the skid."
        )

        for row_index in range(st.session_state.north_row_count):
            default_value = ""

            if row_index == 0:
                default_value = "1-10"

            st.text_input(
                f"LBD North Row {row_index + 1}",
                value=default_value,
                key=f"north_row_{row_index}",
                help=(
                    "Use individual LBD numbers separated by spaces or a range. "
                    "Examples: 1 2 3 4 5 or 1-5."
                )
            )

        north_button_1, north_button_2 = st.columns(2)

        with north_button_1:
            if st.button("➕ Add North Row"):
                st.session_state.north_row_count += 1
                st.rerun()

        with north_button_2:
            if st.button("➖ Remove North Row"):
                if st.session_state.north_row_count > 1:
                    st.session_state.north_row_count -= 1
                    st.rerun()

        st.markdown("---")
        st.subheader("South LBD Rows")

        st.caption(
            "South priority: the first row added is closest to the skid."
        )

        for row_index in range(st.session_state.south_row_count):
            default_value = ""

            if row_index == 0:
                default_value = "11-13"

            st.text_input(
                f"LBD South Row {row_index + 1}",
                value=default_value,
                key=f"south_row_{row_index}",
                help=(
                    "Use individual LBD numbers separated by spaces or a range. "
                    "Examples: 11 12 13 14 15 or 11-15."
                )
            )

        south_button_1, south_button_2 = st.columns(2)

        with south_button_1:
            if st.button("➕ Add South Row"):
                st.session_state.south_row_count += 1
                st.rerun()

        with south_button_2:
            if st.button("➖ Remove South Row"):
                if st.session_state.south_row_count > 1:
                    st.session_state.south_row_count -= 1
                    st.rerun()

    st.markdown("---")
    run_button = st.button("Run Distribution")


# ============================================================
# HEADER
# ============================================================
st.markdown("<div class='main-block'>", unsafe_allow_html=True)

logo_path = Path("rrc.png")

if logo_path.exists():
    st.image(str(logo_path), width=85)

st.markdown(
    """
    <div class="card">
        <h2>TMEIC Skid DC Circuit Distribution</h2>
        <p>
            Physical-aware distribution of LBD circuits across skid inverters.
            The tool balances total strings and ILR while minimizing North/South
            circuit crossings.
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="card">
        <h3>Optimization Logic</h3>
        <ol>
            <li>Minimize the maximum inverter loading deviation.</li>
            <li>Minimize total loading variation between inverters.</li>
            <li>Minimize the number of North/South circuit crossings.</li>
            <li>For equivalent solutions, select crossings closest to the skid.</li>
        </ol>
        <p>
            North rows are prioritized from the last added row toward the first row.
            South rows are prioritized from the first added row toward the last row.
        </p>
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# RESULTS
# ============================================================
if run_button:
    try:
        string_quantities = parse_string_quantities(string_input)

        total_inverters = (
            int(number_inverters_north)
            + int(number_inverters_south)
        )

        if total_inverters <= 0:
            raise ValueError(
                "At least one inverter must be configured."
            )

        if physical_layout_enabled:
            north_rows = []

            for row_index in range(st.session_state.north_row_count):
                row_text = st.session_state.get(
                    f"north_row_{row_index}",
                    ""
                )
                north_rows.append(parse_lbd_row(row_text))

            south_rows = []

            for row_index in range(st.session_state.south_row_count):
                row_text = st.session_state.get(
                    f"south_row_{row_index}",
                    ""
                )
                south_rows.append(parse_lbd_row(row_text))

        else:
            north_rows = []
            south_rows = []

        lbd_data = build_lbd_metadata(
            string_quantities=string_quantities,
            north_rows=north_rows,
            south_rows=south_rows,
            physical_layout_enabled=physical_layout_enabled
        )

        inverters = build_inverters(
            number_north=int(number_inverters_north),
            number_south=int(number_inverters_south)
        )

        assignment, objective = find_best_distribution(
            lbd_data=lbd_data,
            inverters=inverters,
            physical_layout_enabled=physical_layout_enabled
        )

        summary_df, assignment_df = build_result_tables(
            lbd_data=lbd_data,
            assignment=assignment,
            inverters=inverters,
            modules_per_string=modules_per_string,
            module_power_w=module_power_w,
            inverter_power_kva=inverter_power_kva,
            physical_layout_enabled=physical_layout_enabled
        )

        total_strings = summary_df["Total Strings"].sum()
        average_strings = total_strings / len(summary_df)
        min_strings = summary_df["Total Strings"].min()
        max_strings = summary_df["Total Strings"].max()
        max_string_difference = max_strings - min_strings

        ilr_mean = summary_df["ILR"].mean()
        ilr_min = summary_df["ILR"].min()
        ilr_max = summary_df["ILR"].max()
        ilr_std = summary_df["ILR"].std()

        crossing_df = assignment_df[
            assignment_df["Crossing Required"] == "Yes"
        ].copy()

        crossing_count = len(crossing_df)

        # ====================================================
        # SUMMARY METRICS
        # ====================================================
        st.markdown("## Distribution Summary")

        metric_col_1, metric_col_2, metric_col_3, metric_col_4, metric_col_5 = st.columns(5)

        metric_col_1.metric(
            "Total LBDs",
            len(lbd_data)
        )

        metric_col_2.metric(
            "Total Strings",
            total_strings
        )

        metric_col_3.metric(
            "Average Strings / Inverter",
            f"{average_strings:.2f}"
        )

        metric_col_4.metric(
            "Max String Difference",
            max_string_difference
        )

        metric_col_5.metric(
            "Crossing Circuits",
            crossing_count if physical_layout_enabled else "N/A"
        )

        st.markdown("")

        ilr_col_1, ilr_col_2, ilr_col_3, ilr_col_4 = st.columns(4)

        ilr_col_1.metric("Mean ILR", f"{ilr_mean:.3f}")
        ilr_col_2.metric("Min ILR", f"{ilr_min:.3f}")
        ilr_col_3.metric("Max ILR", f"{ilr_max:.3f}")
        ilr_col_4.metric("ILR Std. Dev.", f"{ilr_std:.3f}")

        # ====================================================
        # INVERTER SUMMARY
        # ====================================================
        st.markdown("## Inverter Summary")

        st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True
        )

        chart_col_1, chart_col_2 = st.columns(2)

        with chart_col_1:
            st.markdown("### Strings per Inverter")

            string_chart_df = summary_df.set_index("Inverter")[["Total Strings"]]
            st.bar_chart(string_chart_df)

        with chart_col_2:
            st.markdown("### ILR per Inverter")

            ilr_chart_df = summary_df.set_index("Inverter")[["ILR"]]
            st.bar_chart(ilr_chart_df)

        # ====================================================
        # LBD ASSIGNMENT TABLE
        # ====================================================
        st.markdown("## LBD Circuit Assignment")

        st.dataframe(
            assignment_df,
            use_container_width=True,
            hide_index=True
        )

        # ====================================================
        # CROSSING CIRCUITS
        # ====================================================
        if physical_layout_enabled:
            st.markdown("## Crossing Circuits")

            if crossing_df.empty:
                st.success(
                    "No North/South circuit crossings were required for the selected balance."
                )
            else:
                crossing_df = crossing_df.sort_values(
                    by=[
                        "Distance to Skid",
                        "Strings",
                        "LBD"
                    ],
                    ascending=[
                        True,
                        False,
                        True
                    ]
                )

                st.warning(
                    f"{crossing_count} circuit(s) cross between the North and South sides "
                    f"to improve or maintain inverter loading balance."
                )

                st.dataframe(
                    crossing_df,
                    use_container_width=True,
                    hide_index=True
                )

        # ====================================================
        # DOWNLOADS
        # ====================================================
        st.markdown("## Download Results")

        download_col_1, download_col_2 = st.columns(2)

        with download_col_1:
            st.download_button(
                label="Download Inverter Summary CSV",
                data=summary_df.to_csv(index=False).encode("utf-8"),
                file_name="tmeic_inverter_summary.csv",
                mime="text/csv"
            )

        with download_col_2:
            st.download_button(
                label="Download LBD Assignment CSV",
                data=assignment_df.to_csv(index=False).encode("utf-8"),
                file_name="tmeic_lbd_assignment.csv",
                mime="text/csv"
            )

    except Exception as error:
        st.error(f"Error: {error}")

st.markdown("</div>", unsafe_allow_html=True)
