import SimpleITK as sitk
import os

# PNG 폴더 → 3D Volume 변환
png_dir = "./GT_TEST/Mask_spleen2"
reader = sitk.ImageSeriesReader()

file_names = [os.path.join(png_dir, f) for f in sorted(os.listdir(png_dir)) if f.endswith(".png")]

image = sitk.ReadImage(file_names)

sitk.WriteImage(image, "segmentation_png.nrrd")
