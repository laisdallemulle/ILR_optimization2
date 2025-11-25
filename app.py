import streamlit as st
import pandas as pd
import base64  # <<< NOVO

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
body {
    background-color: #0e1117;
    color: #f5f5f5;
}
.main-block {
    max-width: 1200px;
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
    margin: 0;
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
.dataframe td, .dataframe th {
    color: #f5f5f5 !important;
    background-color: #161a23 !important;
}

/* LOGO E TÍTULO CENTRALIZADOS */
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
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ============================================================
#  FUNÇÃO PARA CARREGAR IMAGEM EM BASE64
# ============================================================
def load_image_base64(path):
    with open(path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

# ============================================================
#  CORE ALGORITHM
# ============================================================
def distribute_str_qty_greedy(str_qty, num_inverters):
    """
    Greedy distribution of string quantities into a given number of inverters.
    The algorithm assigns the next highest string value to the inverter
    with the lowest current sum, balancing the load.
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

    default_str = "16,16,16,16,16,16,16,16,14,14,16,16,16,16,16,16,16,16"
    str_input = st.text_input(
        "String quantities (comma separated)",
        value=default_str
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
#  HEADER AREA (WITH LOCAL LOGO)
# ============================================================
st.markdown("<div class='main-block'>", unsafe_allow_html=True)

# carrega o logo local em base64
logo_b64 = load_image_base64("rrc.png")

st.markdown(
    f"""
    <div class="logo-container">
        <img src="data:image/png;base64,{logo_b64}" class="logo-img">
        <p style="color:#bbbbbb; font-size:13px; margin-top:6px; margin-bottom: inherit;">
            Created by Laís de Oliveira Dalle Mulle – PV Engineer
        </p>
         <p style="color:#bbbbbb; font-size:13px; margin-top:1px;">
            LaisDalleMulle@RRCcompanies.com
        </p>
        <h1 style="color:white; margin-bottom:0;">String Distribution Analyzer</h1>
        <p style="color:#bbbbbb; font-size:15px; margin-top:4px;">
            Greedy allocation of DC strings to balance inverter ILR
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
        This tool distributes DC strings across inverters using a greedy algorithm.
        The goal is to balance total strings, DC power, and ILR across all inverters.
    </p>
    <b>Outputs:</b>
    <ul>
        <li>Strings assigned to each inverter</li>
        <li>DC power per inverter (kW)</li>
        <li>ILR for each inverter</li>
        <li>ILR statistics: mean, min, max, std deviation</li>
        <li>Summary table and charts</li>
    </ul>
</div>
""",
    unsafe_allow_html=True
)

# ============================================================
#  RESULTS
# ============================================================
if run_button:
    try:
        str_qty = [int(x.strip()) for x in str_input.split(",") if x.strip()]

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

        # ILR statistics
        ilr_mean = df_summary["ILR"].mean()
        ilr_min = df_summary["ILR"].min()
        ilr_max = df_summary["ILR"].max()
        ilr_std = df_summary["ILR"].std()

        st.markdown(
            f"""
            <div class="card">
                <h3>ILR Statistics</h3>
                <p><b>Mean ILR:</b> {ilr_mean:.3f}</p>
                <p><b>Min ILR:</b> {ilr_min:.3f}</p>
                <p><b>Max ILR:</b> {ilr_max:.3f}</p>
                <p><b>Std Dev:</b> {ilr_std:.3f}</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Per-inverter cards
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
                        <p><b>Total Strings:</b> {row['Total Strings']}</p>
                        <p><b>DC Power:</b> {row['DC Power (kW)']:.2f} kW</p>
                        <p><b>ILR:</b> {row['ILR']:.3f}</p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        # Table and charts
        col_table, col_plot1 = st.columns([0.5,0.7])

        with col_table:
            st.markdown("<div class='card'><h3>Summary Table</h3></div>", unsafe_allow_html=True)
            st.dataframe(df_summary.set_index("Inverter"))

        with col_plot1:
            st.markdown("<div class='card'><h3>Strings per Inverter</h3></div>", unsafe_allow_html=True)
            st.bar_chart(df_summary.set_index("Inverter")["Total Strings"])

        col_plot2, _ = st.columns([1, 0.01])

        with col_plot2:
            st.markdown("<div class='card'><h3>ILR per Inverter</h3></div>", unsafe_allow_html=True)
            st.bar_chart(df_summary.set_index("Inverter")["ILR"])

    except Exception as e:
        st.error(f"Error: {e}")

st.markdown("</div>", unsafe_allow_html=True)
