# TMEIC Skid DC Circuit Distribution

Streamlit application for distributing DC circuits across TMEIC skid inverters while balancing inverter loading and minimizing unnecessary North/South circuit crossings.

## Features

- Balances total strings, DC power, and inverter loading ratio (ILR).
- Supports separate North and South inverter quantities.
- Assigns LBDs by physical North/South rows.
- Prioritizes LBDs closest to the skid when crossings are required.
- Identifies and lists circuits assigned across the skid.
- Exports inverter summary and LBD assignment results to CSV.

## Requirements

```bash
pip install streamlit pandas
```

## Run the Application

Save the Python application as `app.py`, then run:

```bash
streamlit run app.py
```

## Input Format

### String quantities

Enter quantities separated by spaces. Values are assigned sequentially:

```text
20 20 20 16 16
```

This corresponds to:

```text
LBD01 = 20
LBD02 = 20
LBD03 = 20
LBD04 = 16
LBD05 = 16
```

### LBD rows

Enter individual LBD numbers or ranges:

```text
1 2 3 4 5
```

or:

```text
1-5
```

For North rows, the last added row is considered closest to the skid. For South rows, the first added row is considered closest to the skid.

## Optimization Priority

1. Minimize maximum inverter loading deviation.
2. Minimize overall loading variation.
3. Minimize North/South circuit crossings.
4. Prefer crossing circuits closest to the skid.

## Example TMEIC Configuration

For a five-inverter skid with three South inverters and two North inverters:

```text
Number of inverters North: 2
Number of inverters South: 3

LBD North Row 1: 1-10
LBD South Row 1: 11-15
```

The application assigns Inv 1 through Inv 3 to the South side and Inv 4 through Inv 5 to the North side.
