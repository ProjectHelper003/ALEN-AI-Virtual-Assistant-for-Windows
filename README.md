1 Clone the Repository
git clone https://github.com/YOUR-USERNAME/YOUR-REPO.git
cd YOUR-REPO

2 Add the Wake-Word Model
Place this file in the project directory:
hey-alen_en_windows_v3_0_0.ppn

3 Update Wake-word File Path in Code (optional)

Open alen_virtual_assistant.py and update:
PPN_PATH = r"C:\...\hey-alen_en_windows_v3_0_0.ppn"

Replace with your actual local path OR keep the file in the same directory and use:
PPN_PATH = "hey-alen_en_windows_v3_0_0.ppn"

4 Run ALEN
python alen_virtual_assistant.py

Now ALEN will start listening for:
👉 “Hey Alen”

<img width="1918" height="992" alt="image" src="https://github.com/user-attachments/assets/97aefcc8-ba9f-4a91-9b01-c255a0384332" />

<img width="1918" height="1002" alt="image" src="https://github.com/user-attachments/assets/1bec388b-12b3-4486-9ba2-1d5296dee500" />

