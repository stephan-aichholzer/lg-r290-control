#!/bin/bash
# Generate PNG images from PlantUML files

echo "Generating PlantUML diagrams..."

# Check if plantuml is available
if command -v plantuml &> /dev/null; then
    echo "Using local plantuml installation"
    plantuml UML/*.puml -tpng
elif command -v docker &> /dev/null; then
    echo "Using Docker plantuml/plantuml image"
    docker run --rm -v $(pwd)/UML:/data plantuml/plantuml:latest -tpng /data/*.puml
else
    echo "ERROR: Neither plantuml nor docker found."
    echo "Install with: sudo apt install plantuml"
    echo "Or use Docker: docker pull plantuml/plantuml"
    exit 1
fi

echo "Done! PNG files created in UML/ directory"
ls -lh UML/*.png 2>/dev/null || echo "No PNG files found. Check for errors above."
