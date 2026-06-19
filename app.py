import streamlit as st
import pandas as pd
import re
import os
import base64

# ============================================================
# PAGE CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="Physical-Aware Inverter Balance",
    page_icon="🔌",
    layout="wide"
)

# ============================================================
# CUSTOM CSS
# ============================================================
custom_css = """
<style>
body {
    background-color: #0e1117;
    color: #f5f5f5;
}

.main-block {
    max-width: 1400px;
    margin: 0 auto;
}

.card {
    background-color: #161a23;
    border-radius: 10px;
    padding: 18px 22px;
    margin-bottom: 16px;
    border: 1px solid #262b3a;
}

.card h3 {
    margin-top: 0;
    color: #f5f5f5;
}

.stButton > button {
    background-color: #ff4b4b;
    color: white;
    border-radius: 6px;
    border: none;
    padding: 0.5rem 1rem;
    font-weight: 600;
}

.stButton > button:hover {
    background-color: #ff6b6b;
}

[data-testid="stSidebar"] {
    background-color: #161a23;
}

.stTextInput input,
.stNumberInput input {
    background-color: #0e1117 !important;
    color: #ffffff !important;
}

.logo-container {
    text-align: center;
    margin-top: 20px;
}

.logo-img {
    width: 90px;
    display: block;
    margin-left: auto;
    margin-right: auto;
}

.crossing-yes {
    color: #ff6961;
    font-weight: bold;
}

.crossing-no {
    color: #77dd77;
    font-weight: bold;
}
</style>
"""

st.markdown(custom_css, unsafe_allow_html=True)

# ============================================================
# OPTIONAL LOGO FUNCTION
# ============================================================
def load_image_base64(path):
    if not os.path.exists(path):
        return None

    with open(path, "rb") as file:
        return base64.b64encode(file.read()).decode()

# ============================================================
# INPUT PARSING FUNCTIONS
# ============================================================
def parse_string_quantities(raw_text):
    """
    Expected format:
    20 20 20 16 16 20

    Returns:
    [20, 20, 20, 16, 16, 20]
    """
    raw_text = raw_text.strip()

    if not raw_text:
        raise ValueError("String quantities cannot be empty.")

    values = raw_text.split()

    try:
        quantities = [int(value) for value in values]
    except ValueError:
        raise ValueError(
            "String quantities must contain integers separated by spaces only."
        )

    if any(value <= 0 for value in quantities):
        raise ValueError("All string quantities must be greater than zero.")

    return quantities


def parse_lbd_selection(raw_text, max_lbd):
    """
    Accepted examples:
    1 2 3 4 5
    1-5
    1 2 5-8 12

    Returns:
    set of LBD numbers
    """
    raw_text = raw_text.strip()

    if not raw_text:
        return set()

    normalized_text = raw_text.replace("–", "-").replace("—", "-")
    normalized_text = re.sub(r"\s*-\s*", "-", normalized_text)

    selected_lbds = set()
    tokens = normalized_text.split()

    for token in tokens:
        if "-" in token:
            parts = token.split("-")

            if len(parts) != 2:
                raise ValueError(
                    f"Invalid LBD range '{token}'. Use formats such as 1-5."
                )

            start = int(parts[0])
            end = int(parts[1])

            if start > end:
                raise ValueError(
                    f"Invalid range '{token}'. The first number must be smaller."
                )

            for number in range(start, end + 1):
                selected_lbds.add(number)

        else:
            selected_lbds.add(int(token))

    invalid_lbds = [
        number for number in selected_lbds
        if number < 1 or number > max_lbd
    ]

    if invalid_lbds:
        raise ValueError(
            f"LBD numbers outside the available range 1-{max_lbd}: {invalid_lbds}"
        )

    return selected_lbds


# ============================================================
# INVERTER / CIRCUIT DATA FUNCTIONS
# ============================================================
def build_inverters(num_inverters_south, num_inverters_north):
    """
    Example:
    South = 3
    North = 2

    Result:
    Inv 1 = South
    Inv 2 = South
    Inv 3 = South
    Inv 4 = North
    Inv 5 = North
    """
    inverters = []

    inverter_number = 1

    for _ in range(num_inverters_south):
        inverters.append({
            "name": f"Inv {inverter_number}",
            "side": "South"
        })
        inverter_number += 1

    for _ in range(num_inverters_north):
        inverters.append({
            "name": f"Inv {inverter_number}",
            "side": "North"
        })
        inverter_number += 1

    return inverters


def build_circuits(string_quantities, lbd_north, lbd_south):
    circuits = []

    for index, quantity in enumerate(string_quantities, start=1):
        if index in lbd_north:
            side = "North"
        elif index in lbd_south:
            side = "South"
        else:
            side = "Unassigned"

        circuits.append({
            "lbd_number": index,
            "lbd_name": f"LBD{index:02d}",
            "strings": quantity,
            "side": side
        })

    return circuits


def is_crossing(circuit_side, inverter_side):
    """
    Unassigned LBDs are considered neutral.
    """
    if circuit_side == "Unassigned":
        return False

    return circuit_side != inverter_side


# ============================================================
# BALANCING / OPTIMIZATION FUNCTIONS
# ============================================================
def calculate_metrics(assignments, circuits, inverters):
    inverter_sums = [0] * len(inverters)
    crossings = 0

    for circuit_index, inverter_index in enumerate(assignments):
        circuit = circuits[circuit_index]
        inverter = inverters[inverter_index]

        inverter_sums[inverter_index] += circuit["strings"]

        if is_crossing(circuit["side"], inverter["side"]):
            crossings += 1

    total_strings = sum(inverter_sums)
    target_strings = total_strings / len(inverters)

    max_strings = max(inverter_sums)
    min_strings = min(inverter_sums)

    string_range = max_strings - min_strings

    sum_squared_error = sum(
        (value - target_strings) ** 2
        for value in inverter_sums
    )

    return {
        "sums": inverter_sums,
        "target": target_strings,
        "range": string_range,
        "sse": sum_squared_error,
        "crossings": crossings
    }


def get_balance_key(metrics):
    """
    Lower values are better.

    Priority:
    1. Lower maximum difference between inverter string totals
    2. Lower deviation from target average
    """
    return (
        metrics["range"],
        round(metrics["sse"], 8)
    )


def get_full_key(metrics):
    """
    Used after physical-side preference is enabled.

    Priority:
    1. Electrical balance
    2. Lower deviation from average
    3. Fewer crossings
    """
    return (
        metrics["range"],
        round(metrics["sse"], 8),
        metrics["crossings"]
    )


def initial_physical_assignment(circuits, inverters, use_physical_preference):
    """
    Initial greedy distribution.

    When physical preference is active:
    - North LBDs go first to North inverters
    - South LBDs go first to South inverters
    - Unassigned LBDs can go anywhere
    """
    assignments = [-1] * len(circuits)
    inverter_sums = [0] * len(inverters)

    sorted_circuit_indices = sorted(
        range(len(circuits)),
        key=lambda index: circuits[index]["strings"],
        reverse=True
    )

    for circuit_index in sorted_circuit_indices:
        circuit = circuits[circuit_index]

        if use_physical_preference and circuit["side"] in ["North", "South"]:
            valid_inverters = [
                index
                for index, inverter in enumerate(inverters)
                if inverter["side"] == circuit["side"]
            ]

            # If there are no inverters on that side,
            # the circuit must cross to the opposite side.
            if not valid_inverters:
                valid_inverters = list(range(len(inverters)))
        else:
            valid_inverters = list(range(len(inverters)))

        selected_inverter = min(
            valid_inverters,
            key=lambda inverter_index: inverter_sums[inverter_index]
        )

        assignments[circuit_index] = selected_inverter
        inverter_sums[selected_inverter] += circuit["strings"]

    return assignments


def improve_without_new_crossings(circuits, inverters, assignments):
    """
    Improves inverter balance while maintaining same-side preference.
    It does not create additional crossings.
    """
    max_iterations = len(circuits) * len(inverters) * 5
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        current_metrics = calculate_metrics(assignments, circuits, inverters)
        current_key = get_balance_key(current_metrics)

        best_move = None
        best_key = current_key

        for circuit_index, circuit in enumerate(circuits):
            current_inverter = assignments[circuit_index]

            for candidate_inverter in range(len(inverters)):
                if candidate_inverter == current_inverter:
                    continue

                candidate_inverter_side = inverters[candidate_inverter]["side"]

                # Do not create a crossing during this phase.
                if is_crossing(circuit["side"], candidate_inverter_side):
                    continue

                candidate_assignments = assignments.copy()
                candidate_assignments[circuit_index] = candidate_inverter

                candidate_metrics = calculate_metrics(
                    candidate_assignments,
                    circuits,
                    inverters
                )

                candidate_key = get_balance_key(candidate_metrics)

                if candidate_key < best_key:
                    best_key = candidate_key
                    best_move = candidate_assignments

        if best_move is None:
            break

        assignments = best_move

    return assignments


def improve_with_crossings_if_needed(circuits, inverters, assignments):
    """
    Allows cross-side assignments only when they improve the
    electrical balance of the inverter set.

    A crossing will not be added merely for convenience.
    It must reduce the inverter imbalance.
    """
    max_iterations = len(circuits) * len(inverters) * 10
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        current_metrics = calculate_metrics(assignments, circuits, inverters)
        current_key = get_full_key(current_metrics)

        best_move = None
        best_key = current_key

        for circuit_index, circuit in enumerate(circuits):
            current_inverter = assignments[circuit_index]

            for candidate_inverter in range(len(inverters)):
                if candidate_inverter == current_inverter:
                    continue

                candidate_assignments = assignments.copy()
                candidate_assignments[circuit_index] = candidate_inverter

                candidate_metrics = calculate_metrics(
                    candidate_assignments,
                    circuits,
                    inverters
                )

                candidate_key = get_full_key(candidate_metrics)

                # A new crossing is accepted only if total electrical
                # balance improves enough to reduce the optimization key.
                if candidate_key < best_key:
                    best_key = candidate_key
                    best_move = candidate_assignments

        if best_move is None:
            break

        assignments = best_move

    return assignments


def get_assignment_reason(
    circuit,
    inverter,
    original_assignment,
    final_assignment,
    circuit_index,
    inverters
):
    crossing = is_crossing(circuit["side"], inverter["side"])

    if circuit["side"] == "Unassigned":
        return "LBD physical side was not defined."

    if not crossing:
        return "Assigned to an inverter on the same physical side."

    same_side_inverters = [
        item for item in inverters
        if item["side"] == circuit["side"]
    ]

    if not same_side_inverters:
        return "Crossing required because there is no inverter on the LBD physical side."

    if original_assignment[circuit_index] != final_assignment[circuit_index]:
        return "Crossing added because it improved the overall inverter balance."

    return "Cross-side allocation required by available inverter configuration."


# ============================================================
# SIDEBAR INPUTS
# ============================================================
with st.sidebar:
    st.header("Input Parameters")

    string_input = st.text_input(
        "String quantities (space separated)",
        value="20 20 20 20 20 20 20 20 20 16 20 16 16",
        help=(
            "Example: 20 20 20 16. "
            "The first value represents LBD01, the second LBD02, and so on."
        )
    )

    lbd_north_input = st.text_input(
        "LBD North",
        value="1-10",
        help="Examples: 1-10 or 1 2 3 4 5 6 7 8 9 10"
    )

    lbd_south_input = st.text_input(
        "LBD South",
        value="11-13",
        help="Examples: 11-15 or 11 12 13 14 15"
    )

    num_inverters_north = st.number_input(
        "Number of inverters North",
        min_value=0,
        step=1,
        value=2
    )

    num_inverters_south = st.number_input(
        "Number of inverters South",
        min_value=0,
        step=1,
        value=3
    )

    power_inverter = st.number_input(
        "Inverter AC power (kVA)",
        min_value=0.0,
        step=10.0,
        value=1100.0
    )

    str_moduleqty = st.number_input(
        "Modules per string",
        min_value=1,
        step=1,
        value=27
    )

    pot_module = st.number_input(
        "Module power (W)",
        min_value=1.0,
        step=5.0,
        value=625.0
    )

    use_physical_preference = st.checkbox(
        "Prioritize North/South physical allocation",
        value=True,
        help=(
            "When selected, the tool first keeps LBDs on the same side "
            "as their assigned inverter and allows crossings only when "
            "they improve electrical balance."
        )
    )

    st.markdown("---")

    run_button = st.button("Run Distribution")


# ============================================================
# HEADER
# ============================================================
st.markdown("<div class='main-block'>", unsafe_allow_html=True)

# carrega o logo local em base64
logo_b64 = load_image_base64("rrc.png")

st.markdown(
    f"""
    <div class="logo-container">
        <img src="data:image/png;base64,{logo_b64}" class="logo-img">
        <p style="color:#bbbbbb; font-size:13px; margin-top:6px; margin-bottom: inherit;">
            Created by Laís Dalle Mulle – PV Engineer
        </p>
         <p style="color:#bbbbbb; font-size:13px; margin-top:1px;">
            LaisDalleMulle@RRCcompanies.com
        </p>
        <h1 style="color:white; margin-bottom:0;">Inverter Loading Ratio Calculation</h1>
        <p style="color:#bbbbbb; font-size:15px; margin-top:4px;">
            Greedy allocation of DC strings to balance inverter ILR
        </p>
    </div>
    """,
    unsafe_allow_html=True
)


st.markdown(
    """
    <div class="card">
        <h3>Allocation Logic</h3>
        <p>
            The tool first assigns North LBDs to North inverters and South LBDs to South
            inverters. It then improves the balance while maintaining the same-side preference.
            Cross-side circuits are only added when they improve the overall inverter loading balance.
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
        # --------------------------------------------------------
        # Parse inputs
        # --------------------------------------------------------
        string_quantities = parse_string_quantities(string_input)

        total_lbds = len(string_quantities)

        lbd_north = parse_lbd_selection(
            lbd_north_input,
            total_lbds
        )

        lbd_south = parse_lbd_selection(
            lbd_south_input,
            total_lbds
        )

        if lbd_north.intersection(lbd_south):
            overlap = sorted(lbd_north.intersection(lbd_south))

            raise ValueError(
                f"The following LBDs were assigned to both North and South: {overlap}"
            )

        total_inverters = num_inverters_north + num_inverters_south

        if total_inverters <= 0:
            raise ValueError(
                "At least one North or South inverter must be defined."
            )

        # --------------------------------------------------------
        # Build circuit and inverter objects
        # --------------------------------------------------------
        circuits = build_circuits(
            string_quantities,
            lbd_north,
            lbd_south
        )

        inverters = build_inverters(
            num_inverters_south,
            num_inverters_north
        )

        # --------------------------------------------------------
        # Allocation process
        # --------------------------------------------------------
        original_assignments = initial_physical_assignment(
            circuits,
            inverters,
            use_physical_preference
        )

        assignments = original_assignments.copy()

        if use_physical_preference:
            assignments = improve_without_new_crossings(
                circuits,
                inverters,
                assignments
            )

            assignments = improve_with_crossings_if_needed(
                circuits,
                inverters,
                assignments
            )
        else:
            assignments = improve_with_crossings_if_needed(
                circuits,
                inverters,
                assignments
            )

        # --------------------------------------------------------
        # Metrics
        # --------------------------------------------------------
        final_metrics = calculate_metrics(
            assignments,
            circuits,
            inverters
        )

        inverter_sums = final_metrics["sums"]

        # --------------------------------------------------------
        # Summary table
        # --------------------------------------------------------
        summary_data = []

        for inverter_index, inverter in enumerate(inverters):
            total_strings = inverter_sums[inverter_index]

            dc_power_kw = (
                total_strings
                * str_moduleqty
                * (pot_module / 1000.0)
            )

            ilr = (
                dc_power_kw / power_inverter
                if power_inverter > 0
                else 0
            )

            assigned_circuits = [
                circuits[circuit_index]
                for circuit_index, assigned_inverter in enumerate(assignments)
                if assigned_inverter == inverter_index
            ]

            crossing_count = sum(
                1
                for circuit in assigned_circuits
                if is_crossing(circuit["side"], inverter["side"])
            )

            summary_data.append({
                "Inverter": inverter["name"],
                "Inverter Side": inverter["side"],
                "Total Strings": total_strings,
                "DC Power (kW)": round(dc_power_kw, 2),
                "ILR": round(ilr, 3),
                "Crossing Circuits": crossing_count
            })

        df_summary = pd.DataFrame(summary_data)

        # --------------------------------------------------------
        # Circuit assignment table
        # --------------------------------------------------------
        assignment_data = []

        for circuit_index, circuit in enumerate(circuits):
            inverter_index = assignments[circuit_index]
            inverter = inverters[inverter_index]

            crossing = is_crossing(
                circuit["side"],
                inverter["side"]
            )

            reason = get_assignment_reason(
                circuit,
                inverter,
                original_assignments,
                assignments,
                circuit_index,
                inverters
            )

            assignment_data.append({
                "LBD": circuit["lbd_name"],
                "Strings": circuit["strings"],
                "LBD Side": circuit["side"],
                "Assigned Inverter": inverter["name"],
                "Inverter Side": inverter["side"],
                "Crossing": "YES" if crossing else "NO",
                "Assignment Reason": reason
            })

        df_assignments = pd.DataFrame(assignment_data)

        # --------------------------------------------------------
        # Statistics
        # --------------------------------------------------------
        ilr_mean = df_summary["ILR"].mean()
        ilr_min = df_summary["ILR"].min()
        ilr_max = df_summary["ILR"].max()
        ilr_std = df_summary["ILR"].std()

        unassigned_lbds = [
            circuit["lbd_name"]
            for circuit in circuits
            if circuit["side"] == "Unassigned"
        ]

        # --------------------------------------------------------
        # Display general results
        # --------------------------------------------------------
        st.markdown("## Allocation Summary")

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Total LBDs",
            total_lbds
        )

        col2.metric(
            "Total Inverters",
            total_inverters
        )

        col3.metric(
            "Final String Difference",
            f"{final_metrics['range']} strings"
        )

        col4.metric(
            "Crossing Circuits",
            final_metrics["crossings"]
        )

        if unassigned_lbds:
            st.warning(
                "The following LBDs were not assigned to North or South and were "
                f"treated as physically neutral: {', '.join(unassigned_lbds)}"
            )

        st.markdown(
            f"""
            <div class="card">
                <h3>ILR Statistics</h3>
                <p><b>Mean ILR:</b> {ilr_mean:.3f}</p>
                <p><b>Min ILR:</b> {ilr_min:.3f}</p>
                <p><b>Max ILR:</b> {ilr_max:.3f}</p>
                <p><b>ILR Standard Deviation:</b> {ilr_std:.3f}</p>
                <p><b>Target Strings per Inverter:</b> {final_metrics["target"]:.2f}</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # --------------------------------------------------------
        # Per-inverter cards
        # --------------------------------------------------------
        st.markdown("## Inverter Distribution")

        cols = st.columns(2)

        for inverter_index, inverter in enumerate(inverters):
            col = cols[inverter_index % 2]

            assigned_rows = df_assignments[
                df_assignments["Assigned Inverter"] == inverter["name"]
            ]

            assigned_lbds = assigned_rows["LBD"].tolist()
            crossing_lbds = assigned_rows[
                assigned_rows["Crossing"] == "YES"
            ]["LBD"].tolist()

            summary_row = df_summary.iloc[inverter_index]

            with col:
                crossing_text = (
                    ", ".join(crossing_lbds)
                    if crossing_lbds
                    else "None"
                )

                st.markdown(
                    f"""
                    <div class="card">
                        <h3>{inverter["name"]} – {inverter["side"]}</h3>
                        <p><b>Assigned LBDs:</b> {", ".join(assigned_lbds)}</p>
                        <p><b>Total Strings:</b> {summary_row["Total Strings"]}</p>
                        <p><b>DC Power:</b> {summary_row["DC Power (kW)"]:.2f} kW</p>
                        <p><b>ILR:</b> {summary_row["ILR"]:.3f}</p>
                        <p><b>Crossing LBDs:</b> {crossing_text}</p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        # --------------------------------------------------------
        # Tables and Charts
        # --------------------------------------------------------
        st.markdown("## Inverter Summary Table")
        st.dataframe(
            df_summary.set_index("Inverter"),
            use_container_width=True
        )

        st.markdown("## Circuit Assignment Table")

        def highlight_crossings(row):
            if row["Crossing"] == "YES":
                return [
                    "background-color: #5a1f1f; color: #ffffff;"
                    for _ in row
                ]

            return [
                ""
                for _ in row
            ]

        st.dataframe(
            df_assignments.style.apply(
                highlight_crossings,
                axis=1
            ),
            use_container_width=True
        )

        crossings_df = df_assignments[
            df_assignments["Crossing"] == "YES"
        ].copy()

        st.markdown("## Crossing Circuits")

        if crossings_df.empty:
            st.success(
                "No cross-side circuits were required. All LBDs were allocated "
                "to inverters on the same physical side."
            )
        else:
            st.warning(
                "The following circuits cross between the North and South sides "
                "of the skid because doing so improved the inverter balance."
            )

            st.dataframe(
                crossings_df[
                    [
                        "LBD",
                        "Strings",
                        "LBD Side",
                        "Assigned Inverter",
                        "Inverter Side",
                        "Assignment Reason"
                    ]
                ],
                use_container_width=True
            )

        st.markdown("## Charts")

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown("### Strings per Inverter")
            st.bar_chart(
                df_summary.set_index("Inverter")["Total Strings"]
            )

        with chart_col2:
            st.markdown("### ILR per Inverter")
            st.bar_chart(
                df_summary.set_index("Inverter")["ILR"]
            )

    except Exception as error:
        st.error(f"Error: {error}")

st.markdown("</div>", unsafe_allow_html=True)
