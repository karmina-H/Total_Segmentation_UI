import nibabel as nib
from totalsegmentator.python_api import totalsegmentator
import os

if __name__ == "__main__":
    input_path = 'CT_samples'
    output_path = 'dcm_output2'
    os.makedirs(output_path, exist_ok=True)
    # option 1: provide input and output as file paths
    totalsegmentator(input_path, output_path, task="total",output_type="nifti")
    
    # option 2: provide input and output as nifti image objects
    # input_img = nib.load(input_path)
    # output_img = totalsegmentator(input_img)
    # nib.save(output_img, output_path)


    '''
    argment:
    input: Union[str, Path, Nifti1Image], output: Union[str, Path, None]=None, ml=False, nr_thr_resamp=1, nr_thr_saving=6,
                     fast=False, nora_tag="None", preview=False, task="total", roi_subset=None,
                     statistics=False, radiomics=False, crop_path=None, body_seg=False,
                     force_split=False, output_type="nifti", quiet=False, verbose=False, test=0,
                     skip_saving=False, device="gpu", license_number=None,
                     statistics_exclude_masks_at_border=True, no_derived_masks=False,
                     v1_order=False, fastest=False, roi_subset_robust=None, stats_aggregation="mean",
                     remove_small_blobs=False, statistics_normalized_intensities=False, 
                     robust_crop=False, higher_order_resampling=False, save_probabilities=None
    
                     

        이미지의 라벨 알고싶을때 
        from totalsegmentator.nifti_ext_header import load_multilabel_nifti

            segmentation_nifti_img, label_map_dict = load_multilabel_nifti(image_path)
    '''