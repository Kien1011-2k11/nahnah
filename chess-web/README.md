# Chess vs Bot

Web app cờ vua chơi với bot Stockfish, chỉnh được elo. Backend Python (Flask), frontend HTML/CSS/JS thuần.

## Cách chạy (cmd/terminal)

1. Cài Python packages:
   ```
   cd chess-web
   pip install -r requirements.txt
   ```

2. Tải Stockfish (không kèm sẵn trong repo vì là file thực thi):
   - Vào https://stockfishchess.org/download/ , tải bản phù hợp hệ điều hành của bạn.
   - Giải nén, đặt file thực thi vào `chess-web/engine/stockfish` (Windows thì `chess-web/engine/stockfish.exe`).
   - Nếu đặt tên/đường dẫn khác, set biến môi trường `STOCKFISH_PATH` trỏ tới file đó trước khi chạy.

3. Chạy server:
   ```
   python app.py
   ```

4. Mở trình duyệt vào `http://localhost:5000`.

## Elo bot

- Kéo thanh trượt elo (400-3000) trước khi chơi.
- Elo <= 1350: có thêm 1.5% cơ hội bot "đi hớ" (blunder) — chọn ngẫu nhiên một nước đi hợp lệ thay vì nước tốt nhất, vì Stockfish tự nó không giả lập được elo dưới ~1320.
- Elo > 1350: dùng `UCI_LimitStrength` + `UCI_Elo` của Stockfish để giới hạn sức mạnh.
