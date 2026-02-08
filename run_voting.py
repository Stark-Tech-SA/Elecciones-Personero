from app import VOTING_PORT, app

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=VOTING_PORT)
