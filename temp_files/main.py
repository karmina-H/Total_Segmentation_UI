# 환경에 pip install TotalSegmentator 이거 설치되어있어야함.

import os
import glob
import subprocess
import sys 

#filename지정하면 해당 파일에서만 segmentation하고 지정안하면 input폴더안에 모든 데이터에 대해서 분할수행

def run_totalsegmentator_on_folder(input_folder, output_folder, file_name=None, task="total_mr"):
    # 출력 폴더가 없으면 생성
    os.makedirs(output_folder, exist_ok=True)
    print(f"결과는 '{output_folder}' 폴더에 저장됩니다.")

    if file_name is None:
        ct_files = glob.glob(os.path.join(input_folder, "*.nii")) + \
                glob.glob(os.path.join(input_folder, "*.nii.gz"))
    else:
        ct_files = glob.glob(os.path.join(input_folder,file_name,".nii")) + \
                glob.glob(os.path.join(input_folder, file_name, ".nii.gz"))
        
    # input_file예외처리
    if not ct_files:
        print(f"'{input_folder}'에서 처리할 CT 파일을 찾을 수 없습니다.")
        return

    print(f"총 {len(ct_files)}개의 파일을 처리합니다.")
    # 현재 파이썬 실행 파일의 경로를 기반으로 TotalSegmentator 명령어의 전체 경로를 찾습니다. -> 아나콘다 사용하기떄문
    python_exe_path = sys.executable #  python_exe_path : C:\Users\gusdb\anaconda3\envs\TotalSegmentator\python.exe
    scripts_path = os.path.join(os.path.dirname(python_exe_path), 'Scripts') # python_exe_path : C:\Users\gusdb\anaconda3\envs\TotalSegmentator\Scripts
    totalseg_exe_path = os.path.join(scripts_path, 'TotalSegmentator.exe') # python_exe_path : C:\Users\gusdb\anaconda3\envs\TotalSegmentator\Scripts\TotalSegmentator.exe

    # 환경 예외처리
    if not os.path.exists(totalseg_exe_path):
        print(f"오류: '{totalseg_exe_path}' 에서 TotalSegmentator 실행 파일을 찾을 수 없습니다.")
        return


    for ct_file_path in ct_files:
        # os.path.basename은 전체 경로에서 파일 이름만 추출합니다.
        file_name = os.path.basename(ct_file_path)
        
        # 출력 파일의 전체 경로를 지정합니다.
        # --ml 옵션을 사용하면 폴더가 아닌 단일 파일로 결과가 저장됩니다.
        output_file_path = os.path.join(output_folder, file_name)

        print(f"\n[{file_name}] 파일 처리 시작...")

        # TotalSegmentator 명령어 리스트를 구성합니다.
        command = [
            totalseg_exe_path,
            "-i", ct_file_path,      # 입력 파일
            "-o", output_file_path,  # 출력 파일
            #"--ml"                  
            # "--fast"               
            "--task", task 
        ]

        try:
            # check=True는 명령어 실행 중 오류가 발생하면 예외를 발생시킵니다.
            subprocess.run(command, check=True, text=True)
            print(f"✔️ [{file_name}] 처리 완료. 결과 저장: {output_file_path}")

        except FileNotFoundError:
            print("오류: 'TotalSegmentator' 명령어를 찾을 수 없습니다.")
            print("TotalSegmentator가 설치되어 있고 시스템 PATH에 등록되어 있는지 확인하세요.")
            print("설치 명령어: pip install TotalSegmentator")
            break
        except subprocess.CalledProcessError as e:
            print(f"❌ [{file_name}] 처리 중 오류 발생.")
            print(f"오류 내용: {e.stderr}")
            continue # 다음 파일 처리 계속

    print("\n모든 작업이 완료되었습니다.")


if __name__ == "__main__":
    # 입력 폴더와 출력 폴더를 지정합니다.
    INPUT_CT_FOLDER = "CT_samples"
    OUTPUT_SEG_FOLDER = "segmentation_results"
    
    # 함수를 호출하여 실행합니다.
    run_totalsegmentator_on_folder(INPUT_CT_FOLDER, OUTPUT_SEG_FOLDER)