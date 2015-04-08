import webapp2, json, time
from model import User, Poll, Question, Choice, UserAnswers, DataMocker, DATASTORE_KEY, WeightSolver

class ApiHandler(webapp2.RequestHandler):
    def get(self):
        method = self.request.get('method', 'none')
        userOrNone = self.getUserOrNone()
        self.response.headers.add_header("Access-Control-Allow-Origin", "*")
        self.response.headers.add_header("Access-Control-Allow-Headers", "Content-Type,Access-Control-Allow-Origin,Access-Control-Allow-Headers,Accept,Access-Control-Allow-Methods,X-Requested-With")
        self.response.headers['Content-Type'] = 'application/jsonp'
        # self.response.headers['Content-Type'] = 'text/plain'
        if (method=='populateFakeData'):
            self.populateFakeData()
        elif (method=='getMostRecentPoll'):
            self.getMostRecentPoll(userOrNone)
        elif (method=='getAllPolls'):
            self.getAllPolls(userOrNone)
        #elif (method=='vote'): for easy browser debugging
        #   self.postUserVote()
        elif (method=='calculateWeights'):
            ws = WeightSolver()
            ws.calculateWeights()
            self.response.out.write('Successfully calculated weights!')
        elif (method=='getUsers'):
            self.getUsers(userOrNone)
        elif (method=='none'):
            self.response.out.write('No method was selected')
        else:
            self.response.out.write('Method does not exist')

    def options(self):
        self.get()

    def post(self):
        method = self.request.get('method', 'none')
        self.response.headers.add_header("Access-Control-Allow-Origin", "*")
        self.response.headers.add_header("Access-Control-Allow-Headers", "*")
        self.response.headers['Content-Type'] = 'application/jsonp'
        # self.response.headers['Content-Type'] = 'text/plain'
        if method=='vote':
            self.postUserVote()
        elif method=='user':
            self.newUser()
        elif (method=='none'):
            self.response.out.write('No method was selected')
        else:
            self.response.out.write('Method does not exist')

    def newUser(self):
        email = self.request.get('email', None)
        name = self.request.get('name', None)
        picture = self.request.get('picture', None)
        user = User(parent=DATASTORE_KEY, email=email, name=name, picture=picture)
        user.put()
        self.response.out.write(json.dumps(self.userToJson(user)))

    def getUsers(self, userOrNone):
        query = User.query()
        if (userOrNone is not None):
            query = User.query(User.email != userOrNone.email)
        users = query.fetch()
        userJsons = map(lambda user: self.userToJson(user), users)
        self.response.out.write(json.dumps(userJsons))


    def postUserVote(self):
        user = self.getUserOrNone()     
        question_id = self.request.get('question_id', None)
        choice_id = self.request.get('choice_id', None)
        choice_numeric = self.request.get('choice_numeric', None)
        if (user is None):
            self.response.out.write(json.dumps(
            {
                'status': 'FAILURE',
                'info': 'user_email required',
            }))
            return
        if (question_id is None):
            self.response.out.write(json.dumps(
            {
                'status': 'FAILURE',
                'info': 'question_id required',
            }))
            return
        if (choice_id is None and choice_numeric == None):
            self.response.out.write(json.dumps(
            {
                'status': 'FAILURE',
                'info': 'choice_id or choice_numeric required',
            }))
            return
        if (choice_id is not None and choice_numeric is not None):
            self.response.out.write(json.dumps(
            {
                'status': 'FAILURE',
                'info': 'Only one of {choice_id, choice_numeric} should be stated',
            }))
            return
        
        # Invalidate old votes
        oldVotes = (UserAnswers.query().
            filter(UserAnswers._properties["question"]==int(question_id)).
            filter(UserAnswers._properties["user"]==user.key.integer_id()).
            filter(UserAnswers._properties["isUpToDate"]==True).fetch())

        for oldVote in oldVotes:
            oldVote.isUpToDate = False
            oldVote.put()

        # Create new choice vote
        newVote = None
        if (choice_id is not None):
            newVote = UserAnswers(parent=DATASTORE_KEY,question=int(question_id),user=user.key.integer_id(),choice=int(choice_id))
        elif (choice_numeric is not None):   
            newVote = UserAnswers(parent=DATASTORE_KEY,question=int(question_id),user=user.key.integer_id(),number=int(choice_numeric))
        
        # Store in db
        newVote.put()
        self.response.out.write(json.dumps(
            {
                'status': 'SUCCESS',
                'user_email': user.email,
                'question_id': newVote.question,
                'choice_id': newVote.choice,
                'number': newVote.number,
                'timestamp': time.mktime(newVote.updatedOn.timetuple()) * 1000 + newVote.updatedOn.microsecond / 1000
,
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
        self.response.out.write('Just populated fake data with user emails:\n'+ '\n'.join(str(e) for e in emails))

    def getMostRecentPoll(self, opt_user):
        mostRecentPoll = Poll.query().order(-Poll.publishedOn).get()
        self.response.out.write(json.dumps(self. pollToJson(mostRecentPoll, opt_user)))

    def getAllPolls(self, opt_user):
        polls = Poll.query().fetch()
        pollsJsons = map(lambda poll: self.pollToJson(poll, opt_user), polls)
        self.response.out.write(json.dumps(pollsJsons))

    def choiceToJson(self, choice, opt_user):
        res = {
            'id': choice.key.integer_id(),
            'text': choice.text,
            'raw_votes': choice.getNumberOfSupporters(),
            'reweighted_votes': choice.getWeightOfSupporters(),
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

    def userToJson(self, user):
        return {
            'id': user.keyInteger,
            'email': user.email,
            'name': user.name,
            'weight': user.weight,
            'picture': user.picture,
        }


            












