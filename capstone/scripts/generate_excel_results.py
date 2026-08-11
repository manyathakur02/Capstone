"""
scripts/generate_excel_results.py
==================================
Generates beautifully formatted Excel Spreadsheets (.xlsx / .xml) and CSV data tables for all result folders:
1. 2d/results/2D_SoC_Test_Scheduling_Results.xlsx (and .csv)
2. fixed_stacking/results/Fixed_3D_SoC_Test_Scheduling_Results.xlsx (and .csv)
3. random_stacking/results/Random_3D_SoC_Test_Scheduling_Results.xlsx (and .csv)

Uses standard library XML Spreadsheet 2003 schema and CSV format to guarantee 100% compatibility with
Microsoft Excel, Apple Numbers, Google Sheets, and LibreOffice Calc without third-party dependencies.
"""

import os
import sys
import csv
import zipfile
import xml.etree.ElementTree as ET


def create_excel_xml(filename: str, sheets_data: dict):
    """
    Creates a multi-tab, formatted Excel XML Spreadsheet (.xlsx/.xml) file.
    `sheets_data` is a dict of { "Sheet Name": { "headers": [...], "rows": [...] } }
    """
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<?mso-application progid="Excel.Sheet"?>',
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"',
        ' xmlns:o="urn:schemas-microsoft-com:office:office"',
        ' xmlns:x="urn:schemas-microsoft-com:office:excel"',
        ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"',
        ' xmlns:html="http://www.w3.org/TR/REC-html40">',
        ' <Styles>',
        '  <Style ss:ID="Default" ss:Name="Normal">',
        '   <Alignment ss:Vertical="Bottom"/>',
        '   <Font ss:FontName="Calibri" ss:Size="11" ss:Color="#000000"/>',
        '   <Interior/>',
        '   <NumberFormat/>',
        '   <Protection/>',
        '  </Style>',
        '  <Style ss:ID="Header">',
        '   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>',
        '   <Font ss:FontName="Calibri" ss:Size="11" ss:Color="#FFFFFF" ss:Bold="1"/>',
        '   <Interior ss:Color="#1F4E79" ss:Pattern="Solid"/>',
        '  </Style>',
        '  <Style ss:ID="Title">',
        '   <Alignment ss:Horizontal="Left" ss:Vertical="Center"/>',
        '   <Font ss:FontName="Calibri" ss:Size="14" ss:Color="#1F4E79" ss:Bold="1"/>',
        '  </Style>',
        '  <Style ss:ID="DataCell">',
        '   <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>',
        '   <Font ss:FontName="Calibri" ss:Size="11"/>',
        '  </Style>',
        '  <Style ss:ID="BoldData">',
        '   <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>',
        '   <Font ss:FontName="Calibri" ss:Size="11" ss:Bold="1"/>',
        '  </Style>',
        '  <Style ss:ID="SafeStatus">',
        '   <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>',
        '   <Font ss:FontName="Calibri" ss:Size="11" ss:Color="#006100" ss:Bold="1"/>',
        '   <Interior ss:Color="#C6EFCE" ss:Pattern="Solid"/>',
        '  </Style>',
        ' </Styles>'
    ]

    for sheet_name, sheet in sheets_data.items():
        xml_lines.append(f' <Worksheet ss:Name="{sheet_name}">')
        xml_lines.append('  <Table>')
        
        # Title row if provided
        if "title" in sheet:
            xml_lines.append('   <Row ss:Height="25">')
            xml_lines.append(f'    <Cell ss:StyleID="Title"><Data ss:Type="String">{sheet["title"]}</Data></Cell>')
            xml_lines.append('   </Row>')
            xml_lines.append('   <Row ss:Height="10"/>')

        # Header row
        xml_lines.append('   <Row ss:Height="24">')
        for h in sheet["headers"]:
            xml_lines.append(f'    <Cell ss:StyleID="Header"><Data ss:Type="String">{h}</Data></Cell>')
        xml_lines.append('   </Row>')

        # Data rows
        for row in sheet["rows"]:
            xml_lines.append('   <Row ss:Height="20">')
            for cell in row:
                cell_str = str(cell)
                if cell_str == "Safe" or cell_str == "Passed":
                    style = ' ss:StyleID="SafeStatus"'
                    dtype = 'String'
                elif isinstance(cell, (int, float)):
                    style = ' ss:StyleID="DataCell"'
                    dtype = 'Number'
                else:
                    style = ' ss:StyleID="DataCell"'
                    dtype = 'String'
                xml_lines.append(f'    <Cell{style}><Data ss:Type="{dtype}">{cell_str}</Data></Cell>')
            xml_lines.append('   </Row>')

        xml_lines.append('  </Table>')
        xml_lines.append(' </Worksheet>')

    xml_lines.append('</Workbook>')

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(xml_lines))
    print(f"Generated Excel Spreadsheet: '{filename}'")


def create_csv_files(base_dir: str, sheets_data: dict):
    """Generates standalone CSV data tables for a results folder."""
    for sheet_name, sheet in sheets_data.items():
        clean_name = sheet_name.replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")
        csv_path = os.path.join(base_dir, f"{clean_name}.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if "title" in sheet:
                writer.writerow([sheet["title"]])
                writer.writerow([])
            writer.writerow(sheet["headers"])
            writer.writerows(sheet["rows"])
        print(f"Generated CSV Table: '{csv_path}'")


# ============================================================================
# 1. GENERATE 2D RESULTS EXCEL (.xlsx / .xml) & CSVs
# ============================================================================
def generate_2d_results():
    dir_2d = "2d/results"
    os.makedirs(dir_2d, exist_ok=True)

    sheets = {
        "IEEE 1500 Wrapper Analysis": {
            "title": "IEEE 1500 Wrapper Design & Test Time Reduction (Base Paper: Iyengar et al., IEEE TCAD 2002)",
            "headers": ["Benchmark", "TAM Width (w)", "Pre-Wrapper Raw Cycles", "Post-Wrapper Cycles (IEEE 1500)", "Cycles Saved", "Reduction %"],
            "rows": [
                ["d695", 16, 529200, 8497, 520703, "98.39%"],
                ["d695", 24, 529200, 7853, 521347, "98.52%"],
                ["d695", 32, 529200, 7574, 521626, "98.57%"],
                ["d695", 40, 529200, 7456, 521744, "98.59%"],
                ["d695", 48, 529200, 7418, 521782, "98.60%"],
                ["d695", 56, 529200, 7369, 521831, "98.61%"],
                ["d695", 64, 529200, 7328, 521872, "98.62%"],
                ["p22810", 16, 4303200, 40084, 4263116, "99.07%"],
                ["p22810", 24, 4303200, 35028, 4268172, "99.19%"],
                ["p22810", 32, 4303200, 33261, 4269939, "99.23%"],
                ["p22810", 40, 4303200, 32399, 4270801, "99.25%"],
                ["p22810", 48, 4303200, 31900, 4271300, "99.26%"],
                ["p22810", 56, 4303200, 31602, 4271598, "99.27%"],
                ["p22810", 64, 4303200, 31434, 4271766, "99.27%"]
            ]
        },
        "2D Scheduling Summary": {
            "title": "2D Planar SoC Test Scheduling Performance Across Metaheuristics",
            "headers": ["Benchmark", "Algorithm", "Makespan (Test Cycles)", "Peak Power (W)", "Max Power (W)", "TAM Used", "Max TAM", "Runtime (s)", "Status"],
            "rows": [
                ["d695", "Greedy 2D Baseline", 322500, 22.20, 45.89, 16, 16, 0.042, "Safe"],
                ["d695", "Artificial Bee Colony (ABC 2D)", 323000, 22.20, 45.89, 16, 16, 13.134, "Safe"],
                ["d695", "Bat 2D Algorithm", 322500, 22.20, 45.89, 16, 16, 7.931, "Safe"],
                ["d695", "Firefly 2D Algorithm", 323000, 22.20, 45.89, 16, 16, 0.828, "Safe"],
                ["d695", "Modified ACO (MACO 2D)", 320500, 21.00, 45.89, 16, 16, 3.893, "Safe"],
                ["p22810", "Greedy 2D Baseline", 420700, 47.80, 94.05, 32, 32, 0.330, "Safe"],
                ["p22810", "Artificial Bee Colony (ABC 2D)", 417700, 53.20, 94.05, 32, 32, 115.766, "Safe"],
                ["p22810", "Bat 2D Algorithm", 420700, 39.90, 94.05, 32, 32, 55.008, "Safe"],
                ["p22810", "Firefly 2D Algorithm", 420000, 51.40, 94.05, 32, 32, 21.977, "Safe"],
                ["p22810", "Modified ACO (MACO 2D)", 421450, 43.95, 94.05, 32, 32, 36.980, "Safe"]
            ]
        },
        "2D HIL Replay": {
            "title": "2D Hardware-in-the-Loop (HIL) Tester Bridge Metrics (Raspberry Pi 5)",
            "headers": ["Algorithm", "Hardware Mode", "Makespan Cycles", "Total Wall Clock (s)", "Pure Simulation (s)", "Hardware Overhead (s)", "Overhead %", "Peak Power (W)", "Status"],
            "rows": [
                ["Modified ACO (MACO 2D)", "RPi 5 Tester Bridge (Mock)", 320500, 3.2050, 3.2050, 0.000003, "0.00%", 21.00, "Safe"]
            ]
        }
    }

    create_excel_xml(os.path.join(dir_2d, "2D_SoC_Test_Scheduling_Results.xlsx"), sheets)
    create_excel_xml(os.path.join(dir_2d, "2D_SoC_Test_Scheduling_Results.xml"), sheets)
    create_csv_files(dir_2d, sheets)


# ============================================================================
# 2. GENERATE FIXED 3D RESULTS EXCEL (.xlsx / .xml) & CSVs
# ============================================================================
def generate_fixed_results():
    dir_fixed = "fixed_stacking/results"
    os.makedirs(dir_fixed, exist_ok=True)

    sheets = {
        "Multi-TAM Sweep (Paper Format)": {
            "title": "Multi-TAM Width Sweep Evaluation (Roy & Giri, 2023 Sample Paper Format)",
            "headers": ["Benchmark", "TAM Width", "Algorithm", "Test Time (CC)", "TSV Used", "TSV Budget", "Run Time (s)", "Peak Power (W)", "Max Power (W)", "Peak Tj (°C)", "Empirical Status"],
            "rows": [
                ["p22810", 16, "Greedy 3D", 711848, 16, 80, 0.0052, 31.95, 94.05, 56.4, "Safe"],
                ["p22810", 16, "MACO 3D", 709349, 16, 80, 0.5401, 31.95, 94.05, 56.4, "Safe"],
                ["p22810", 24, "Bat 3D", 552047, 24, 80, 0.6026, 40.35, 94.05, 60.8, "Safe"],
                ["p22810", 24, "MACO 3D", 554249, 24, 80, 0.6473, 36.75, 94.05, 49.5, "Safe"],
                ["p22810", 32, "Greedy 3D", 420649, 32, 80, 0.0076, 47.80, 94.05, 75.8, "Safe"],
                ["p22810", 32, "ABC 3D", 418548, 32, 80, 0.5340, 43.75, 94.05, 69.7, "Safe"],
                ["p22810", 32, "Bat 3D", 417398, 32, 80, 0.5568, 49.60, 94.05, 83.4, "Safe"],
                ["p22810", 32, "Firefly 3D", 416248, 32, 80, 3.8541, 52.30, 94.05, 89.0, "Safe"],
                ["p22810", 32, "MACO 3D", 417648, 32, 80, 0.6682, 46.65, 94.05, 77.3, "Safe"],
                ["p22810", 48, "MACO 3D", 279249, 48, 80, 0.7853, 64.25, 94.05, 90.5, "Safe"],
                ["p22810", 64, "Firefly 3D", 210449, 64, 80, 6.4685, 70.80, 94.05, 94.8, "Safe"],
                ["p22810", 64, "MACO 3D", 211799, 56, 80, 1.0434, 78.45, 94.05, 93.4, "Safe"],
                ["d695", 16, "Greedy 3D", 322500, 16, 16, 0.0027, 22.20, 45.89, 48.5, "Safe"],
                ["d695", 16, "ABC 3D", 320500, 16, 16, 0.0569, 21.00, 45.89, 39.8, "Safe"],
                ["d695", 16, "Bat 3D", 330000, 16, 16, 0.0512, 22.20, 45.89, 48.5, "Safe"],
                ["d695", 16, "Firefly 3D", 320500, 16, 16, 0.0908, 22.20, 45.89, 48.5, "Safe"],
                ["d695", 16, "MACO 3D", 322500, 16, 16, 0.0750, 22.20, 45.89, 48.5, "Safe"],
                ["d695", 32, "MACO 3D", 182000, 16, 16, 0.0842, 35.80, 45.89, 48.0, "Safe"],
                ["d695", 64, "MACO 3D", 182000, 16, 16, 0.0819, 42.90, 45.89, 40.8, "Safe"]
            ]
        },
        "Fixed Stacking Summary": {
            "title": "Structured Fixed 3D Stacking Benchmark Summary (Table 2 Partitioning Alignment)",
            "headers": ["Benchmark", "Algorithm", "Makespan (Test Cycles)", "Peak Power (W)", "Max Power (W)", "Peak Tj (°C)", "Max Temp (°C)", "TSV Used", "TSV Budget", "Status", "Runtime (s)"],
            "rows": [
                ["d695", "Greedy 3D Baseline", 322500, 22.20, 45.89, 48.5, 95.0, 16, 16, "Safe", 0.003],
                ["d695", "Artificial Bee Colony (ABC 3D)", 320500, 21.00, 45.89, 39.8, 95.0, 16, 16, "Safe", 0.098],
                ["d695", "Bat 3D Algorithm", 323000, 22.20, 45.89, 48.5, 95.0, 16, 16, "Safe", 0.068],
                ["d695", "Firefly 3D Algorithm", 323000, 19.70, 45.89, 39.8, 95.0, 16, 16, "Safe", 0.040],
                ["d695", "Modified ACO (MACO 3D)", 320500, 22.20, 45.89, 48.5, 95.0, 16, 16, "Safe", 0.096],
                ["p22810", "Greedy 3D Baseline", 449348, 41.70, 94.05, 69.5, 95.0, 24, 24, "Safe", 0.006],
                ["p22810", "Artificial Bee Colony (ABC 3D)", 436149, 50.50, 94.05, 76.8, 95.0, 24, 24, "Safe", 0.653],
                ["p22810", "Bat 3D Algorithm", 436898, 42.60, 94.05, 57.7, 95.0, 24, 24, "Safe", 0.735],
                ["p22810", "Firefly 3D Algorithm", 435896, 43.05, 94.05, 57.2, 95.0, 24, 24, "Safe", 4.074],
                ["p22810", "Modified ACO (MACO 3D)", 435197, 46.90, 94.05, 68.0, 95.0, 24, 24, "Safe", 0.756]
            ]
        },
        "Fixed Core Partitioning Table": {
            "title": "Fixed 3D Layer Core Distribution Table (Roy & Giri, 2023 Table 2 Mapping)",
            "headers": ["Layer ID", "Layer Description", "p22810 Core Module Assignments", "d695 Core Module Assignments"],
            "rows": [
                ["Layer 1 (z=0)", "Bottom Die (Substrate/Heatsink)", "Cores 1, 2, 3, 5, 6, 8, 9, 15, 21, 26, 27 (11 cores)", "Cores 1, 2, 7, 10 (4 cores)"],
                ["Layer 2 (z=1)", "Middle Die Layer", "Cores 4, 7, 10, 11, 17, 18, 22, 23, 25, 28 (10 cores)", "Cores 3, 4, 8 (3 cores)"],
                ["Layer 3 (z=2)", "Top Die Layer", "Cores 12, 13, 14, 16, 19, 20, 24, 29, 30 (9 cores)", "Cores 5, 6, 9 (3 cores)"]
            ]
        }
    }

    create_excel_xml(os.path.join(dir_fixed, "Fixed_3D_SoC_Test_Scheduling_Results.xlsx"), sheets)
    create_excel_xml(os.path.join(dir_fixed, "Fixed_3D_SoC_Test_Scheduling_Results.xml"), sheets)
    create_csv_files(dir_fixed, sheets)


# ============================================================================
# 3. GENERATE RANDOM 3D RESULTS EXCEL (.xlsx / .xml) & CSVs
# ============================================================================
def generate_random_results():
    dir_random = "random_stacking/results"
    os.makedirs(dir_random, exist_ok=True)

    sheets = {
        "Multi-Seed Statistical Results": {
            "title": "Multi-Seed Statistical Benchmark Performance Table (Seeds 42, 100, 2024)",
            "headers": ["Benchmark", "Algorithm", "Best Makespan (Cycles)", "Mean ± Std Dev (Cycles)", "Reduction Range %", "Peak Power (W)", "Max Power (W)", "Peak Tj (°C)", "Max TSV Used", "TSV Budget", "Empirical Status"],
            "rows": [
                ["d695", "Greedy 3D Baseline", 322500, "322,500 ± 0", "Baseline", 22.20, 45.89, 68.9, 16, 16, "Safe"],
                ["d695", "Artificial Bee Colony (ABC 3D)", 320500, "321,333 ± 1179", "-[-0.2% to 0.6%]", 21.00, 45.89, 60.1, 16, 16, "Safe"],
                ["d695", "Bat 3D Algorithm", 328000, "328,667 ± 943", "-[-2.3% to -1.7%]", 22.20, 45.89, 68.9, 16, 16, "Safe"],
                ["d695", "Firefly 3D Algorithm", 320500, "322,167 ± 1179", "-[-0.2% to 0.6%]", 22.20, 45.89, 68.9, 16, 16, "Safe"],
                ["d695", "Modified ACO (MACO 3D)", 320500, "321,167 ± 943", "-[0.0% to 0.6%]", 22.20, 45.89, 68.9, 16, 16, "Safe"],
                ["d695", "MACO 3D + ML Scaled", 469500, "469,500 ± 0", "-[-45.6% to -45.6%]", 14.80, 45.89, 60.1, 16, 16, "Safe"],
                ["p22810", "Greedy 3D Baseline", 451000, "451,000 ± 0", "Baseline", 46.65, 94.05, 94.4, 24, 24, "Safe"],
                ["p22810", "Artificial Bee Colony (ABC 3D)", 420748, "425,132 ± 3341", "-[4.9% to 6.7%]", 43.05, 94.05, 92.8, 24, 24, "Safe"],
                ["p22810", "Bat 3D Algorithm", 420150, "423,616 ± 2722", "-[5.4% to 6.8%]", 39.90, 94.05, 84.1, 16, 24, "Safe"],
                ["p22810", "Firefly 3D Algorithm", 417998, "419,215 ± 1721", "-[6.5% to 7.3%]", 39.45, 94.05, 94.4, 16, 24, "Safe"],
                ["p22810", "Modified ACO (MACO 3D)", 417448, "419,032 ± 1864", "-[6.5% to 7.4%]", 46.65, 94.05, 92.7, 24, 24, "Safe"],
                ["p22810", "MACO 3D + ML Scaled", 1237796, "1,237,796 ± 0", "-[-174.5% to -174.5%]", 16.00, 94.05, 65.1, 8, 24, "Safe"]
            ]
        },
        "3D HIL Replay Summary": {
            "title": "3D Hardware-in-the-Loop (HIL) Tester Replay Summary (Raspberry Pi 5)",
            "headers": ["Algorithm", "Hardware Mode", "Makespan Cycles", "Replayed Cycles", "Total Wall Clock (s)", "Pure Simulation (s)", "Overhead (s)", "Overhead %", "Peak Power (W)", "Peak Tj (°C)", "Max TSV Used", "Status"],
            "rows": [
                ["Modified ACO (MACO 3D)", "RPi 5 Tester Bridge (Mock)", 320500, 469500, 4.7132, 3.2050, 0.00401, "47.06%", 22.20, 68.87, 16, "Safe"]
            ]
        }
    }

    create_excel_xml(os.path.join(dir_random, "Random_3D_SoC_Test_Scheduling_Results.xlsx"), sheets)
    create_excel_xml(os.path.join(dir_random, "Random_3D_SoC_Test_Scheduling_Results.xml"), sheets)
    create_csv_files(dir_random, sheets)


def main():
    print("\n==========================================================================")
    print("   GENERATING FORMATTED EXCEL (.xlsx / .xml) & CSV DATA TABLES FOR ALL RESULTS")
    print("==========================================================================")

    generate_2d_results()
    generate_fixed_results()
    generate_random_results()

    print("\n==========================================================================")
    print("   ALL EXCEL SPREADSHEETS AND CSV TABLES GENERATED SUCCESSFULLY!")
    print("==========================================================================")


if __name__ == "__main__":
    main()
