import streamlit as st
import pandas as pd

# ============================================================
#  PAGE CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="Inverter Loading Ratio Calculation", 
    page_icon="🔌",
    layout="wide"
)

# ============================================================
#  CUSTOM CSS (dark dashboard look)
# ============================================================
custom_css = """
<style>
/* Global dark background */
body {
    background-color: #0e1117;
    color: #f5f5f5;
}

/* Main centered block */
.main-block {
    max-width: 1200px;
    margin: 0 auto;
}

/* Generic card style */
.card {
    background-color: #161a23;
    border-radius: 10px;
    padding: 18px 22px;
    margin-bottom: 16px;
    border: 1px solid #262b3a;
}

/* Card title */
.card h3 {
    margin: 0;
    color: #f5f5f5;
}

/* Primary button style */
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

/* Dark sidebar */
[data-testid="stSidebar"] {
    background-color: #161a23;
}

/* Dark inputs */
.stTextInput input,
.stNumberInput input {
    background-color: #0e1117 !important;
    color: #ffffff !important;
}

/* Dataframe cells */
.dataframe td, .dataframe th {
    color: #f5f5f5 !important;
    background-color: #161a23 !important;
}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ============================================================
#  CORE ALGORITHM
# ============================================================
def distribute_str_qty_greedy(str_qty, num_inverters):
    """
    Greedy distribution of string quantities into a given number of inverters.

    The algorithm always assigns the next largest string quantity to the inverter
    with the current lowest total string count, to keep totals as balanced as possible.
    """
    str_qty_sorted = sorted(str_qty, reverse=True)
    lines = [[] for _ in range(num_inverters)]
    sums = [0] * num_inverters

    for number in str_qty_sorted:
        idx = sums.index(min(sums))
        lines[idx].append(number)
        sums[idx] += number

    return lines, sums

# ============================================================
#  SIDEBAR INPUTS
# ============================================================
with st.sidebar:
    st.header("Input Parameters")

    st.write("Enter string and inverter data:")

    default_str = "16,16,16,16,16,16,16,16,14,14,16,16,16,16,16,16,16,16"
    str_input = st.text_input(
        "String quantities (comma separated)",
        value=default_str,
        help="Example: 16,16,16,16,14,14,16..."
    )

    num_inverters = st.number_input(
        "Number of inverters",
        min_value=1,
        step=1,
        value=4
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

    st.markdown("---")
    run_button = st.button("Run Distribution")

# ============================================================
#  HEADER (CENTERED TITLE AND DESCRIPTION)
# ============================================================
st.markdown("<div class='main-block'>", unsafe_allow_html=True)

st.markdown(
    """
    <div style="text-align: center; margin-top: 20px; margin-bottom: 10px;">
        <!-- Replace this link with a local logo if you want -->
        <img src="https://i.imgur.com/8KEvT0p.png" width="90">
        <p style="color:#bbbbbb; font-size:13px; margin-top:6px;">
            Created by Laís de Oliveira Dalle Mulle – PV Engineer
        </p>
        <h1 style="color:white; margin-bottom:0;">String Distribution Analyzer</h1>
        <p style="color:#bbbbbb; font-size:15px; margin-top:4px;">
            Greedy allocation of DC strings to balance inverter ILR
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
<div class="card" style="text-align:center;">
    <p style="margin-bottom:0;">
        Enter the project parameters in the sidebar and click 
        <strong>'Run Distribution'</strong> to see how the strings are balanced among inverters.
    </p>
</div>
""",
    unsafe_allow_html=True
)

# ============================================================
#  ABOUT SECTION
# ============================================================
st.markdown(
    """
<div class="card">
    <h3>About This Application</h3>
    <p>
        This tool distributes DC strings across a specified number of inverters
        using a greedy algorithm. The goal is to keep DC loading as balanced as
        possible and provide an approximate Inverter Loading Ratio (ILR) for each unit.
    </p>
    <b>Inputs:</b>
    <ul>
        <li>String quantities</li>
        <li>Number of inverters</li>
        <li>Modules per string</li>
        <li>Module power (W)</li>
        <li>Inverter AC power (kVA)</li>
    </ul>
    <b>Outputs:</b>
    <ul>
        <li>Allocation of strings per inverter</li>
        <li>Total strings per inverter</li>
        <li>Approximate DC power per inverter (kW)</li>
        <li>ILR (DC/AC) for each inverter</li>
        <li>Summary table and plots</li>
        <li>ILR statistics: mean, min, max, and standard deviation</li>
    </ul>
</div>
""",
    unsafe_allow_html=True
)

# ============================================================
#  RESULTS SECTION
# ============================================================
if run_button:
    try:
        # Parse string list from text input
        str_qty = [int(x.strip()) for x in str_input.split(",") if x.strip()]
        if len(str_qty) == 0:
            st.error("Please provide at least one string quantity.")
        else:
            distributed_lines, line_sums = distribute_str_qty_greedy(str_qty, num_inverters)

            # Build summary DataFrame
            data = []
            for i, total_strings in enumerate(line_sums):
                dc_power_kw = total_strings * str_moduleqty * (pot_module / 1000.0)
                ilr = dc_power_kw / power_inverter if power_inverter > 0 else 0
                data.append({
                    "Inverter": f"Inv {i+1}",
                    "Total Strings": total_strings,
                    "DC Power (kW)": dc_power_kw,
                    "ILR": ilr
                })

            df_summary = pd.DataFrame(data)

            # --------------------------------------------------------
            #  ILR STATISTICS CARD (MEAN / MIN / MAX / STD)
            # --------------------------------------------------------
            ilr_mean = df_summary["ILR"].mean()
            ilr_min = df_summary["ILR"].min()
            ilr_max = df_summary["ILR"].max()
            ilr_std = df_summary["ILR"].std()

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                f"""
                <div class="card">
                    <h3>ILR Statistics</h3>
                    <p><b>Mean ILR:</b> {ilr_mean:.3f}</p>
                    <p><b>Minimum ILR:</b> {ilr_min:.3f}</p>
                    <p><b>Maximum ILR:</b> {ilr_max:.3f}</p>
                    <p><b>Standard Deviation:</b> {ilr_std:.3f}</p>
                </div>
                """,
                unsafe_allow_html=True
            )

            # --------------------------------------------------------
            #  PER-INVERTER CARDS
            # --------------------------------------------------------
            st.markdown("### Distribution Results")
            cols = st.columns(2)
            for idx, row in df_summary.iterrows():
                col = cols[idx % 2]
                with col:
                    st.markdown(
                        f"""
                        <div class="card">
                            <h3>{row['Inverter']}</h3>
                            <p><b>Strings:</b> {distributed_lines[idx]}</p>
                            <p><b>Total strings:</b> {int(row['Total Strings'])}</p>
                            <p><b>DC Power:</b> {row['DC Power (kW)']:.2f} kW</p>
                            <p><b>ILR:</b> {row['ILR']:.3f}</p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

            st.markdown("<br>", unsafe_allow_html=True)

            # --------------------------------------------------------
            #  TABLE + PLOTS
            # --------------------------------------------------------
            col_table, col_plot1 = st.columns([1.1, 1.3])

            with col_table:
                st.markdown(
                    """
                    <div class="card">
                        <h3>Summary Table</h3>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                st.dataframe(df_summary.set_index("Inverter"))

            with col_plot1:
                st.markdown(
                    """
                    <div class="card">
                        <h3>Strings per Inverter</h3>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                st.bar_chart(
                    df_summary.set_index("Inverter")["Total Strings"]
                )

            st.markdown("<br>", unsafe_allow_html=True)

            col_plot2, _ = st.columns([1.3, 0.7])
            with col_plot2:
                st.markdown(
                    """
                    <div class="card">
                        <h3>ILR per Inverter</h3>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                st.bar_chart(
                    df_summary.set_index("Inverter")["ILR"]
                )

    except ValueError:
        st.error("Error parsing string list. Use only integers separated by commas.")
    except Exception as e:
        st.error(f"Unexpected error: {e}")

st.markdown("</div>", unsafe_allow_html=True)
