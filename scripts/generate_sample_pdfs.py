"""
Generates prototype agricultural advisory PDFs using PyMuPDF for testing Phase 2 ingestion.
Contains authentic institutional guidelines from ICAR and KVK standard formats.
"""
from pathlib import Path
import pymupdf


def create_pdf(file_path: Path, title: str, sections: list):
    doc = pymupdf.open()
    page = doc.new_page()

    # Draw header
    p1 = pymupdf.Point(50, 60)
    page.insert_text(p1, title, fontsize=15, fontname="helv", color=(0.1, 0.4, 0.1))

    y = 100
    for header, body in sections:
        # Section Header
        page.insert_text(pymupdf.Point(50, y), header, fontsize=12, fontname="helv", color=(0, 0, 0))
        y += 20

        # Section Body (wrap text)
        rect = pymupdf.Rect(50, y, 550, y + 100)
        page.insert_textbox(rect, body, fontsize=10, fontname="helv", color=(0.2, 0.2, 0.2))
        y += 90

    doc.save(str(file_path))
    doc.close()
    print(f"Created prototype PDF: {file_path}")


def main():
    output_dir = Path("data/raw_documents")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Cotton Pink Bollworm Advisory (Approved ICAR Source)
    cotton_sections = [
        (
            "1. Overview & Monitoring of Pink Bollworm in Cotton",
            "Pink bollworm (Pectinophora gossypiella) is a serious pest affecting cotton crops during the flowering and boll development stages in Maharashtra and central India. Farmers are advised to install 5 sex pheromone traps per hectare for pest monitoring."
        ),
        (
            "2. Cultural & Mechanical Control Measures",
            "Collect and destroy rosette flowers containing larvae. Avoid ratoon cropping and destroy crop residues immediately after the final harvest to break the pest lifecycle. Deep summer plowing helps expose dormant pupae to solar heat and natural predators."
        ),
        (
            "3. Safety and Certified Advisory Notice",
            "Farmers must consult the local Krishi Vigyan Kendra (KVK) or State Agricultural University agronomists before applying any chemical interventions. Never use unapproved tank mixtures. Contact Kisan Call Centre at 1800-180-1551 for official district alerts."
        )
    ]
    create_pdf(
        output_dir / "cotton_pink_bollworm_icar_advisory.pdf",
        "ICAR-CICR Cotton Advisory: Pink Bollworm Management",
        cotton_sections
    )

    # 2. Wheat Yellow Rust Advisory (Approved KVK Source)
    wheat_sections = [
        (
            "1. Identification of Yellow Rust in Wheat",
            "Yellow rust (Puccinia striiformis) appears as bright yellow powdery pustules arranged in linear stripes on the upper leaf surface of wheat crops during cool, humid conditions in Punjab and North-Western plains."
        ),
        (
            "2. Recommended Farm Practices & Surveillance",
            "Inspect wheat fields regularly during January and February, especially in shaded and humid areas. Grow rust-resistant varieties recommended by agricultural universities. Avoid excessive nitrogen application which promotes fungal vulnerability."
        ),
        (
            "3. Official Referral & Immediate Guidance",
            "Upon first symptom detection, report immediately to the district agriculture extension officer or nearest Krishi Vigyan Kendra. For real-time crop disease guidance, call the National Kisan Call Centre toll-free at 1800-180-1551."
        )
    ]
    create_pdf(
        output_dir / "wheat_yellow_rust_kvk_bulletin.pdf",
        "KVK Wheat Advisory: Yellow Rust Surveillance & Field Guidance",
        wheat_sections
    )

    # 3. Unapproved Draft File (Intentionally Draft / Pending Approval)
    draft_sections = [
        (
            "1. Unverified Informal Pesticide Mixes",
            "This document contains unverified farmer field suggestions for mixing chemicals without university trials. It should not be used for official advisory until certified by institutional experts."
        )
    ]
    create_pdf(
        output_dir / "unapproved_draft_notes.pdf",
        "DRAFT: Unverified Field Notes on Chemical Application",
        draft_sections
    )


if __name__ == "__main__":
    main()
