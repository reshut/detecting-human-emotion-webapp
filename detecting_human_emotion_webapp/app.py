from flask import render_template, redirect, url_for, request, g, flash, send_from_directory
from werkzeug.utils import secure_filename
import os
from detecting_human_emotion_webapp import app
from detecting_human_emotion_webapp.forms import UserInfoForm
from okta import UsersClient
from flask_oidc import OpenIDConnect
from deception_detection.audio.lie_detection import classify_file
import platform
okta_client = UsersClient("https://dev-240328.oktapreview.com", "00Axbx-B_Dl0XMqSoQmZlURJv9djfBRjHQ9F2xQ4GT")

ALLOWED_EXTENSIONS = ['wav','mp4','jpg','txt']


AUDIO_DECEPTION_DOMINATE_RESULT = { 0: "Truth", 1: "Lie"}

oidc = OpenIDConnect(app)
if platform.system() is "Windows":

    QUESTIONS = 'detecting_human_emotion_webapp/questions.txt'
else:

    QUESTIONS = 'questions.txt'

@app.before_request
def before_request():
    if oidc.user_loggedin:
        g.user = okta_client.get_user(oidc.user_getfield("sub"))
    else:
        g.user = None


class questions:

    def __init__(self,questions):
        self.questions = questions
        self.currentQuestion = 0

    def getSize(self):
        return len(self.questions)

    def getCurrentQuestion(self):
        question = self.questions[self.currentQuestion]
        self.currentQuestion += 1

        return question


@app.route("/")
def index():

    if oidc.user_loggedin is False:
        return redirect("/login")
    else:
        return redirect("/detecting")


@app.route("/login")
@oidc.require_login
def login():
    # return redirect(url_for(".dashboard"))
    return redirect("/detecting")


@app.route("/logout", methods=["GET","POSt"])
@oidc.require_login
def logout():
    oidc.logout()

    # return redirect(url_for(".login"))
    return redirect("/login")

@app.route("/getUserInfo", methods=["GET"])
def userInfo():
    header = 'Get User Info'
    userInfo = UserInfoForm()
    template_name = "get_user_info.html"
    return render_template(template_name_or_list=template_name, userInfoForm=userInfo, title=header)


@app.route("/getUserInfo", methods=["POST"])
def userInfoPost():
    userInfo = UserInfoForm()
    g.user.profile.race = userInfo.race.data
    g.user.profile.gender = userInfo.gender.data
    g.user.profile.age = userInfo.age

    return redirect("/detecting")


@app.route("/detecting", methods=["GET"])
def recording_start_get():

    header = "Start Detecting Human Emotion"
    template = "startprompt.html"

    prompt = "After clicking on the start button you will be asked a series of question. Once you have read the question please answer to the best of your ability and alaborate on your response."

    return render_template(template_name_or_list=template, header = header, prompt=prompt)


@app.route("/detecting",methods=["POST"])
def recording_start_post():
    g.user.profile.questions = getListFromTextFile(QUESTIONS)
    print(g.user.profile.questions)
    return redirect(url_for('question', questionNumber = 0))

@app.route(f"/detecting/<int:questionNumber>", methods=["GET"])
def question(questionNumber):
    g.user.profile.questions = getListFromTextFile(QUESTIONS)
    # questions = getListFromTextFile(QUESTIONS)
    header = f'Question {questionNumber + 1}'
    template_name = "questions.html"
    #
    q= g.user.profile.questions[questionNumber]

    return render_template(template_name_or_list=template_name,title=header,question=q, numberOfQuestions = str(len(g.user.profile.questions)),currentQuestionNumber = str(questionNumber + 1))



#send video recording file
@app.route("/detecting/<int:questionNumber>", methods=["POST"])
def question_post(questionNumber):
    g.user.profile.questions = getListFromTextFile(QUESTIONS)
    # questions = getListFromTextFile(QUESTIONS)
    questionNumber += 1
    print(questionNumber)
    if questionNumber < len(g.user.profile.questions):
        return redirect(url_for('question', questionNumber = questionNumber))
    else:
        return redirect("/results")

@app.route("/results",methods=["GET"])
def resultsPage():
    header = 'Results Page'
    # userInfo = UserInfoForm()
    template_name = "results_page.html"

    #passing in as an array
    data = getLineFromTextFile(QUESTIONS).split("\n")
    return render_template(template_name_or_list=template_name, data = data, title = header)


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

def getLineFromTextFile(fileName):
    data = ''
    with open(fileName, 'r') as file:
        for line in file:
            data += line

    return data
def getListFromTextFile(fileName):
    l = []
    with open(fileName, 'r') as file:
        for line in file:
            formatted_line = line.strip('\n')
            l.append(formatted_line)

    return l


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# this the uploading method
@app.route("/upload", methods=["GET"])
def upload():
    header = "Uploading a file"
    template = "uploading_page.html"

    prompt = "Here you can upload a file to detect lying"
    return render_template(template_name_or_list=template, header = header, prompt=prompt)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename)

# @app.route('/uploader', methods=['GET', 'POST'])
# def upload_file():
#     if request.method == 'POST':
#         f = request.files['file']
#         f.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f.filename)))
#         return 'file uploaded successfully'

@app.route("/upload", methods=["POST"])
def uploading():
    header = "processing file"
    template = "results_page.html"

    saved_file_location = ""

    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)

    file = request.files['file']

    # if user does not select file, browser also
    # submit a empty part without filename
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file and allowed_file(file.filename):
        saved_file_location = os.path.join(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename)))


        file.save(saved_file_location)
        # return redirect(url_for('uploaded_file',
        #                         filename=file))
    model_path = "deception_detection/audio/deceptionGradientBoosting"
    print(saved_file_location)
    print(os.path.isfile(saved_file_location))
    # print(temp_file)

    audio_deception_results = classify_file(file=saved_file_location,trained_machine_name=model_path)
    audio_deception_results = parse_deception_audio_result(audio_deception_results)
    print(audio_deception_results)
    # SAVE FILE HERE WHICH WAS INPUTED
    results = {"audio_deception_detection": audio_deception_results}
    print(results)

    return render_template(template_name_or_list="file_upload_results.html",results = results)

#     # return redirect(url_for('file_results', results = 1))
def parse_deception_audio_result(results):
    dominate_result_int,result_statistics, paths = results
    dominate_result = AUDIO_DECEPTION_DOMINATE_RESULT.get(dominate_result_int)

    statistics = list(result_statistics)
    new_statistics = []
    for result in result_statistics:
        temp_string = "{:.1%}".format(result)
        new_statistics.append(temp_string)

    return [dominate_result,new_statistics]


#     return list(dominate_results[dominate_result],result_statistics)
# @app.route("/file_results/<int:results>", methods=["POST"])
# def file_results(results):
#     header = 'Results Page'
#     # userInfo = UserInfoForm()
#     template_name = "file_upload_results.html"
#
#     print(results)


    # return render_template(template_name_or_list=template_name, results = results)
# @app.route('/upload')
# def upload_files():
#     return render_template('upload.html')




if __name__ == '__main__':
    app.run(host="localhost",port= 5000)
