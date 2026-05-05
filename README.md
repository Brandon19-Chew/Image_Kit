# Image_Kit
Test the image texture, convert format and adjust elements.


<img width="430" height="325" alt="image" src="https://github.com/user-attachments/assets/43c382e0-06f4-49d6-8392-904c668afc23" />

</br>
Sidebar organization:

 - File operations

 - Format conversion (with dropdown + convert/save options)

 - Live adjustment sliders (brightness, contrast, saturation)

 - JPEG quality compression slider

 - Resize (pixel dimensions + percentage)

 - Rotate & flip icon buttons

 - Filter effects list

 - Base64 import/export

 - Archive compression

 - History (undo) and info display

---

## Key Features

1. Non-destructive Adjustments
   - Sliders modify brightness/contrast/saturation on top of the original image without altering it. Debounced with 55ms delay for smooth updates.

2. Format Conversion
   - Both in-memory conversion (without saving) and "Convert & Save As" which properly handles format-specific requirements (removing alpha for JPEG, palette mode for GIF).

3. History System
   - Each destructive operation pushes to a history list. Undo pops the latest state. Reset restores to the original load point.

4. Theme
   - Dark mode UI with GitHub-inspired color scheme using hex codes defined as constants at the top.

---

pip install image-kit

Image_Kit 
