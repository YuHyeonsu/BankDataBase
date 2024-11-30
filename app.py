from flask import Flask, jsonify, request, render_template, redirect, url_for
import cx_Oracle

app = Flask(__name__)

# Oracle 데이터베이스 연결 설정
dsn_tns = cx_Oracle.makedsn('localhost', 4016, service_name='XE')  # 포트 4016으로 설정
connection = cx_Oracle.connect(
    user='hyeonsu',           # Oracle 사용자 이름
    password='2475',          # Oracle 비밀번호
    dsn=dsn_tns,
    encoding="UTF-8",         # UTF-8로 인코딩 설정
    nencoding="UTF-8"         # NCHAR 인코딩 설정
)

# 홈 페이지
@app.route('/')
def home():
    return render_template('base.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            name = request.form['name']
            phone = request.form['phone']
            address = request.form['address']
            email = request.form['email']

            print(f"Received data - Name: {name}, Phone: {phone}, Address: {address}, Email: {email}")

            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO Customers (CustomerID, Name, Phone, Address, Email) VALUES (Customers_SEQ.NEXTVAL, :1, :2, :3, :4)",
                (name, phone, address, email)
            )
            connection.commit()
            cursor.close()
            print("Data successfully inserted into the database.")

            # 회원가입 성공 후 리디렉션
            print("Redirecting to login page...")
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Error occurred: {e}")
            return render_template('register.html', message='회원가입 중 오류가 발생했습니다.')

    return render_template('register.html')




# 로그인 페이지
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['name']  # 이름 입력
        phone = request.form['phone']  # 전화번호 입력

        # 데이터베이스에서 고객 정보 확인
        cursor = connection.cursor()
        cursor.execute(
            "SELECT CustomerID FROM Customers WHERE Name = :1 AND Phone = :2",
            (name, phone)
        )
        user = cursor.fetchone()
        cursor.close()

        if user:
            # 로그인 성공: 해당 고객 ID의 계좌 페이지로 리디렉션
            customer_id = user[0]
            print(f"Login successful for CustomerID: {customer_id}")
            return redirect(url_for('accounts', customer_id=customer_id))
        else:
            # 로그인 실패: 에러 메시지와 함께 로그인 페이지 다시 렌더링
            print("Login failed: Name or Phone mismatch.")
            return render_template('login.html', error='로그인 실패: 이름 또는 전화번호가 잘못되었습니다.')

    return render_template('login.html')

@app.route('/accounts/<int:customer_id>', methods=['GET', 'POST'])
def accounts(customer_id):
    # 고객 이름 가져오기
    cursor = connection.cursor()
    cursor.execute("SELECT Name FROM Customers WHERE CustomerID = :1", [customer_id])
    customer_name = cursor.fetchone()[0]  # 고객 이름 가져오기
    cursor.close()

    if request.method == 'POST':
        account_type = request.form['account_type']
        balance = request.form['balance']

        # 새로운 계좌 등록
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO Accounts (AccountID, CustomerID, AccountType, Balance) VALUES (Accounts_SEQ.NEXTVAL, :1, :2, :3)",
            (customer_id, account_type, balance)
        )
        connection.commit()
        cursor.close()

    # 고객의 계좌 정보 조회
    cursor = connection.cursor()
    cursor.execute("SELECT AccountID, AccountType, Balance, CreatedAt FROM Accounts WHERE CustomerID = :1", [customer_id])
    accounts = cursor.fetchall()
    cursor.close()

    return render_template('accounts.html', accounts=accounts, customer_name=customer_name, customer_id=customer_id)

@app.route('/transactions/<int:account_id>')
def transactions(account_id):
    try:
        # 계좌 정보 가져오기
        cursor = connection.cursor()
        cursor.execute("SELECT CustomerID, AccountType, Balance FROM Accounts WHERE AccountID = :1", [account_id])
        account_info = cursor.fetchone()

        # 계좌 정보가 없는 경우 처리
        if not account_info:
            return f"No account found with AccountID: {account_id}", 404

        customer_id = account_info[0]  # CustomerID 가져오기
        account_type = account_info[1]
        balance = account_info[2]

        # 거래 내역 조회
        cursor.execute("""
            SELECT TransactionID, TransactionType, Amount, TransactionDate, Description
            FROM Transactions
            WHERE AccountID = :1
        """, [account_id])
        transactions = cursor.fetchall()
        cursor.close()

        return render_template('transactions.html',
                               account_id=account_id,
                               account_info=(account_type, balance),
                               transactions=transactions,
                               customer_id=customer_id)
    except cx_Oracle.DatabaseError as e:
        return jsonify({"error": str(e)}), 500


@app.route('/transfer/<int:account_id>', methods=['GET', 'POST'])
def transfer(account_id):
    if request.method == 'POST':
        try:
            recipient_customer_id = int(request.form['recipient_customer_id'])  # 수신 고객 ID
            recipient_account_id = int(request.form['recipient_account_id'])  # 수신 계좌 ID
            amount = float(request.form['amount'])  # 송금 금액

            print(f"Initiating transfer: Sender Account={account_id}, Recipient Customer={recipient_customer_id}, Recipient Account={recipient_account_id}, Amount={amount}")

            # 송금 계좌 및 수신 계좌 유효성 확인
            cursor = connection.cursor()

            # 송금 계좌 확인
            cursor.execute("SELECT CustomerID, Balance FROM Accounts WHERE AccountID = :1", [account_id])
            sender_account = cursor.fetchone()
            if not sender_account:
                print(f"Sender account {account_id} does not exist.")
                return render_template('transfer.html', error='송금 계좌가 존재하지 않습니다.', account_id=account_id)

            sender_customer_id, sender_balance = sender_account

            # 수신 계좌 확인
            cursor.execute("SELECT CustomerID, Balance FROM Accounts WHERE AccountID = :1 AND CustomerID = :2",
                           [recipient_account_id, recipient_customer_id])
            recipient_account = cursor.fetchone()
            if not recipient_account:
                print(f"Recipient account {recipient_account_id} for customer {recipient_customer_id} does not exist.")
                return render_template('transfer.html', error='수신 계좌 또는 고객 ID가 유효하지 않습니다.', account_id=account_id)

            recipient_balance = recipient_account[1]

            # 송금 계좌 잔액 확인
            if sender_balance >= amount:
                # 송금 계좌 잔액 감소
                cursor.execute(
                    "UPDATE Accounts SET Balance = Balance - :1 WHERE AccountID = :2",
                    [amount, account_id]
                )
                print(f"Amount deducted from sender account: {amount}")

                # 수신 계좌 잔액 증가
                cursor.execute(
                    "UPDATE Accounts SET Balance = Balance + :1 WHERE AccountID = :2",
                    [amount, recipient_account_id]
                )
                print(f"Amount added to recipient account: {amount}")

                # 거래 내역 추가 (송금 내역)
                cursor.execute(
                    """INSERT INTO Transactions (TransactionID, AccountID, TransactionType, Amount, TransactionDate, Description)
                    VALUES (Transactions_SEQ.NEXTVAL, :1, 'TRANSFER', :2, SYSDATE, '송금 (수신 계좌: {})')""".format(recipient_account_id),
                    [account_id, amount]
                )

                # 거래 내역 추가 (입금 내역)
                cursor.execute(
                    """INSERT INTO Transactions (TransactionID, AccountID, TransactionType, Amount, TransactionDate, Description)
                    VALUES (Transactions_SEQ.NEXTVAL, :1, 'DEPOSIT', :2, SYSDATE, '입금 (송금 계좌: {})')""".format(account_id),
                    [recipient_account_id, amount]
                )

                # 송금 계좌의 남은 잔액 확인
                cursor.execute("SELECT Balance FROM Accounts WHERE AccountID = :1", [account_id])
                remaining_balance = cursor.fetchone()[0]

                connection.commit()
                cursor.close()

                print(f"Transfer completed successfully. Remaining balance: {remaining_balance}")

                # 송금 성공 메시지와 결과 반환
                return render_template('transfer_success.html',
                                       sender_account_id=account_id,
                                       recipient_customer_id=recipient_customer_id,
                                       recipient_account_id=recipient_account_id,
                                       amount=amount,
                                       remaining_balance=remaining_balance,
                                       sender_customer_id=sender_customer_id)
            else:
                cursor.close()
                print("잔액 부족")
                return render_template('transfer.html', error='잔액이 부족합니다.', account_id=account_id)
        except Exception as e:
            print(f"오류 발생: {e}")
            return render_template('transfer.html', error=f'오류 발생: {e}', account_id=account_id)

    return render_template('transfer.html', account_id=account_id)


# 고객 정보 조회 (READ)
@app.route('/customers', methods=['GET'])
def get_customers():
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Customers")  # Customers 테이블에서 데이터 가져오기
        rows = cursor.fetchall()
        cursor.close()
        return jsonify(rows)
    except cx_Oracle.DatabaseError as e:
        return jsonify({"error": str(e)}), 500

# 고객 추가 (CREATE)
@app.route('/customers', methods=['POST'])
def add_customer():
    data = request.json
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO Customers (CustomerID, Name, Phone, Address, Email) VALUES (Customers_SEQ.NEXTVAL, :1, :2, :3, :4)",
        (data['name'], data['phone'], data['address'], data['email'])
    )
    connection.commit()
    cursor.close()
    return jsonify({'message': 'Customer added successfully'}), 201

# 고객 삭제 (DELETE)
@app.route('/customers/<int:customer_id>', methods=['DELETE'])
def delete_customer(customer_id):
    cursor = connection.cursor()
    cursor.execute("DELETE FROM Customers WHERE CustomerID = :1", [customer_id])
    connection.commit()
    cursor.close()
    return jsonify({'message': 'Customer deleted successfully'})

# 고객 수정 (UPDATE)
@app.route('/customers/<int:customer_id>', methods=['PUT'])
def update_customer(customer_id):
    data = request.json
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE Customers SET Name = :1, Phone = :2, Address = :3, Email = :4 WHERE CustomerID = :5",
        (data['name'], data['phone'], data['address'], data['email'], customer_id)
    )
    connection.commit()
    cursor.close()
    return jsonify({'message': 'Customer updated successfully'})


# 서버 실행
if __name__ == '__main__':
    app.run(debug=True)
