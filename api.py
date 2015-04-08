import webapp2, json
from model import User, Poll, Question, Choice, UserAnswers, DataMocker, DATASTORE_KEY

class ApiHandler(webapp2.RequestHandler):
    def get(self):
        method = self.request.get('method', 'none')
        userOrNone = self.getUserOrNone()     
        self.response.headers['Content-Type'] = 'text/plain'
        if (method=='populateFakeData'):
            self.populateFakeData()
        elif (method=='getMostRecentPoll'):
            self.getMostRecentPoll(userOrNone)
        elif (method=='getAllPolls'):
            self.getAllPolls(userOrNone)
        elif (method=='none'):
            self.response.write('No method was selected')
        else:
            self.response.write('Method does not exist')

    def post(self):
        method = self.request.get('method', 'none')
        self.response.headers['Content-Type'] = 'text/plain'
        if method=='vote':
            self.userVote()
        elif (method=='none'):
            self.response.write('No method was selected')
        else:
            self.response.write('Method does not exist')

    def userVote(self):
        user = self.getUserOrNone()     
        question_id = self.request.get('question_id', None)
        choice_id = self.request.get('choice_id', None)
        choice_numeric = self.request.get('choice_numeric', None)
        if (user is None):
            self.response.write('user_email required')
        if (question_id is None):
            self.response.write('question_id required')
        if (choice_id is None and choice_numeric == None):
            self.response.write('choice_id or choice_numeric required')
        if (choice_id is not None and choice_numeric is not None):
            self.response.write('ony one of {choice_id, choice_numeric} should be stated')
        
        # Invalidate old votes
        oldVotes = (UserAnswers.query().
            filter(UserAnswers._properties["question"]==question_id).
            filter(UserAnswers._properties["user"]==user.key.integer_id()).
            filter(UserAnswers._properties["isUpToDate"]==True)).fetch()
        for oldVote in oldVotes:
            oldVote.isUpToDate = False
            oldVote.put()

        # Create new choice vote
        newVote = None
        if (choice_id is not None):
            newVote = UserAnswers(parent=DATASTORE_KEY,question=question_id,user=user.key.integer_id(),choice=choice_id)
        elif (choice_numeric is not None):   
            newVote = UserAnswers(parent=DATASTORE_KEY,question=question_id,user=user.key.integer_id(),number=choice_numeric)
        
        # Store in db
        newVote.put()
        self.response.write(json.dumps(
            {
                'status': 'SUCCESS',
                'user_email': user.email,
                'question_id': question_id,
                'choice_id': newVote.choice_id,
                'number': newVote.number,
                'timestamp': newVote.updatedOn.now(),
            }))

    def getUserOrNone(self):
        userEmailOrNone = self.request.get('user_email', None)
        if (userEmailOrNone is None):
            return None
        query = User.query().filter(User._properties["email"]==userEmailOrNone)
        if (query.count() != 1):
            return None
        return query.get()

    def populateFakeData(self):
        dm = DataMocker()
        dm.populateFakeData()
        users = User.query().fetch()
        emails = map(lambda user: user.email, users)
        self.response.write('Just populated fake data with user emails:\n'+ '\n'.join(str(e) for e in emails))

    def getMostRecentPoll(self, opt_user):
        mostRecentPoll = Poll.query().order(-Poll.publishedOn).get()
        self.response.write(json.dumps(self. pollToJson(mostRecentPoll, opt_user)))

    def getAllPolls(self, opt_user):
        polls = Poll.query().fetch()
        pollsJsons = map(lambda poll: self.pollToJson(poll, opt_user), polls)
        self.response.write(json.dumps(pollsJsons))

    def choiceToJson(self, choice, opt_user):
        res = {
            'id': choice.key.integer_id(),
            'text': choice.text,
            'votes': choice.getNumberOfSupporters(),
        }
        if (opt_user):
            res['doesUserSupportChoice'] = self.doesUserSupportChoice(choice, opt_user)
        return res

    def doesUserSupportChoice(self, choice, user):
        query = (UserAnswers.query().
            filter(UserAnswers._properties["choice"]==choice.key.integer_id()).
            filter(UserAnswers._properties["user"]==user.key.integer_id()).
            filter(UserAnswers._properties["isUpToDate"]==True))
        return query.count() == 1

    def getUserNumericalAnswerOrNone(self,question,user):
        query = (UserAnswers.query().
            filter(UserAnswers._properties["question"]==question.key.integer_id()).
            filter(UserAnswers._properties["user"]==user.key.integer_id()).
            order(-UserAnswers.updatedOn))
        if query.count() == 0:
            return None
        return query.get().number

    def questionToJson(self, question, opt_user):
        res = {
            'id': question.key.integer_id(),
            'text': question.text,
            'type': question.questionType
        }
        if question.questionType == "MultipleChoice":
            choices = question.getChoices()
            choicesJsons = map(lambda choice: self.choiceToJson(choice, opt_user), choices)
            res['choices'] = choicesJsons
        elif (question.questionType == "Numeric") and opt_user:
            numericalAnswer = self.getUserNumericalAnswerOrNone(question,opt_user)
            if (numericalAnswer):
                res['selectedNumber'] = numericalAnswer
        return res

    def pollToJson(self, poll, opt_user):
        questions = poll.getQuestions()
        questionJsons = map(lambda question: self.questionToJson(question, opt_user), questions)
        return {
            'id': poll.key.integer_id(),
            'title': poll.title,
            'content': poll.content,
            'publishedOn': poll.publishedOn.strftime("%d/%m/%y"),
            'tags': poll.tags,
            'questions': questionJsons,
        }

            












