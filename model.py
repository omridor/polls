import os
import urllib

from google.appengine.api import users
from google.appengine.ext import ndb

import webapp2

DATASTORE_KEY = ndb.Key('test', 'test')

# We set a parent key on the 'Greetings' to ensure that they are all
# in the same entity group. Queries across the single entity group
# will be consistent.  However, the write rate should be limited to
# ~1/second.


class User(ndb.Model):
    email = ndb.StringProperty(indexed=True)
    name = ndb.StringProperty(indexed=False)
    weight = ndb.FloatProperty(indexed=False,default=1.0)
    keyInteger = ndb.ComputedProperty(lambda self: self.key.integer_id())


class Poll(ndb.Model):
    """A single poll, which may have several questions."""
    title = ndb.StringProperty(indexed=False)
    content = ndb.StringProperty(indexed=False)
    publishedOn = ndb.DateTimeProperty(indexed=True,auto_now_add=True)
    tags = ndb.StringProperty(indexed=True, repeated=True)
    #closedOn = ndb.DateTimeProperty()

    def getQuestions(self):
        return Question.query().filter(Question._properties["poll"]==self.key.integer_id()).fetch()        


class Question(ndb.Model):
    """A question, which will be featured in a single poll."""
    poll = ndb.IntegerProperty(indexed=True)
    text = ndb.StringProperty(indexed=False)
    questionType = ndb.StringProperty(indexed=False, default="MultipleChoice", choices=["MultipleChoice","Numeric"])

    def getChoices(self):
        return Choice.query().filter(Choice._properties["question"]==self.key.integer_id()).fetch()


class Choice(ndb.Model):
    """A main model for representing a single answer."""
    question = ndb.IntegerProperty(indexed=True)
    text = ndb.StringProperty(indexed=True)

    def getNumberOfSupporters(self):
        return UserAnswers.query().filter(UserAnswers._properties["choice"]==self.key.integer_id()).filter(UserAnswers.isUpToDate == True).count()

    def getWeightOfSupporters(self):
        weight = 0
        users = User.query().fetch()
        for user in users:
            query = (UserAnswers.query().
                filter(UserAnswers._properties["choice"]==self.key.integer_id()).
                filter(UserAnswers._properties["user"]==user.key.integer_id()).
                filter(UserAnswers._properties["isUpToDate"]==True))
            if (query.count() == 1):
                weight += user.weight
        return weight


class UserAnswers(ndb.Model):
    """A mapping of users to their selected answers."""
    user = ndb.IntegerProperty(indexed=True)
    question = ndb.IntegerProperty(indexed=True)
    choice = ndb.IntegerProperty(indexed=True)
    updatedOn = ndb.DateTimeProperty(auto_now_add=True)
    number = ndb.IntegerProperty()
    isUpToDate = ndb.BooleanProperty(default=True)


class WeightSolver:

    def calculateWeights(self):
        maleChoice = Choice.query().filter(Choice._properties["text"]=='Male').get()
        self.maleChoiceId = maleChoice.key.integer_id()
        femaleChoice = Choice.query().filter(Choice._properties["text"]=='Female').get()
        self.femaleChoiceId = femaleChoice.key.integer_id()

        # Count males and females
        maleNum = (UserAnswers.query().
            filter(UserAnswers._properties["choice"]==self.maleChoiceId).
            filter(UserAnswers._properties["isUpToDate"]==True)).count()
        
        femaleNum = (UserAnswers.query().
            filter(UserAnswers._properties["choice"]==self.femaleChoiceId).
            filter(UserAnswers._properties["isUpToDate"]==True)).count()

        if femaleNum == 0 or maleNum == 0:
            return
        
        menWomenRatio = maleNum/femaleNum
        users = User.query().fetch()
        for user in users:
            if (self.isFemale(user)):
                user.weight = menWomenRatio
                user.put()


    def isFemale(self,user):
        query = (UserAnswers.query().
            filter(UserAnswers._properties["choice"]==self.femaleChoiceId).
            filter(UserAnswers._properties["user"]==user.key.integer_id()).
            filter(UserAnswers._properties["isUpToDate"]==True))
        return query.count() == 1

class DataMocker:
    def populateFakeData(self):
        # clear all data
        ndb.delete_multi(UserAnswers.query().fetch(keys_only=True))
        ndb.delete_multi(Choice.query().fetch(keys_only=True))
        ndb.delete_multi(Question.query().fetch(keys_only=True))
        ndb.delete_multi(Poll.query().fetch(keys_only=True))
        ndb.delete_multi(User.query().fetch(keys_only=True))


        # 5 users
        self.actualUser = User(parent=DATASTORE_KEY, email = "user0@example.com", name = 'user')
        self.actualUser.put()
        self.user1 = User(parent=DATASTORE_KEY, email = "user1@example.com", name = 'user1')
        self.user1.put()
        self.user2 = User(parent=DATASTORE_KEY, email = "user2@example.com", name = 'user2')
        self.user2.put()
        self.user3 = User(parent=DATASTORE_KEY, email = "user3@example.com", name = 'user3')
        self.user3.put()
        self.user4 = User(parent=DATASTORE_KEY, email = "user4@example.com", name = 'user4')
        self.user4.put()

        self.addControlPoll()
        self.addCorePoll()
        self.addPublicTransportationPoll()

    def addControlPoll(self):
        poll = Poll(parent=DATASTORE_KEY,title="Control Questions", content="These questions help us correct for biases in our sample", tags=['control'])
        poll.put()

        # gender
        gender = Question(parent=DATASTORE_KEY,poll=poll.key.integer_id(),text="Gender",questionType="MultipleChoice")
        gender.put()
        
        # Choices
        male = Choice(parent=DATASTORE_KEY,question=gender.key.integer_id(), text="Male")
        male.put()
        female = Choice(parent=DATASTORE_KEY,question=gender.key.integer_id(), text="Female")
        female.put()

        # UserAnswers
        UserAnswers(parent=DATASTORE_KEY,user=self.user1.key.integer_id(),question=gender.key.integer_id(),choice=male.key.integer_id()).put()
        UserAnswers(parent=DATASTORE_KEY,user=self.user2.key.integer_id(),question=gender.key.integer_id(),choice=male.key.integer_id()).put()
        UserAnswers(parent=DATASTORE_KEY,user=self.user3.key.integer_id(),question=gender.key.integer_id(),choice=male.key.integer_id()).put()
        UserAnswers(parent=DATASTORE_KEY,user=self.user4.key.integer_id(),question=gender.key.integer_id(),choice=female.key.integer_id()).put()
        
        # Age
        age = Question(parent=DATASTORE_KEY,poll=poll.key.integer_id(),text="Year of birth",questionType="Numeric")
        age.put()
        UserAnswers(parent=DATASTORE_KEY,user=self.user1.key.integer_id(),question=age.key.integer_id(),number=20).put()
        UserAnswers(parent=DATASTORE_KEY,user=self.user2.key.integer_id(),question=age.key.integer_id(),number=23).put()
        UserAnswers(parent=DATASTORE_KEY,user=self.user3.key.integer_id(),question=age.key.integer_id(),number=60).put()
        UserAnswers(parent=DATASTORE_KEY,user=self.user4.key.integer_id(),question=age.key.integer_id(),number=27).put()

    def addCorePoll(self):
        poll = Poll(parent=DATASTORE_KEY,title="Core issues",tags=['core'])
        poll.put()

        arabConflict = Question(parent=DATASTORE_KEY,poll=poll.key.integer_id(),text="What do you think is the best feasable long term solution to the Israeli Palastinian conflict?",questionType="MultipleChoice")
        arabConflict.put()
        statusQuo = Choice(parent=DATASTORE_KEY,question=arabConflict.key.integer_id(), text="Maintaining the current status quo: No Palastinian state, no voting rights for Palastinias")
        statusQuo.put()
        twoStates = Choice(parent=DATASTORE_KEY,question=arabConflict.key.integer_id(), text="Palastinians should have their own state, based roughly on the 67 borders. Most settlements will be dismantled to allow for territorial continuity.")
        twoStates.put()
        twoStatesPartial = Choice(parent=DATASTORE_KEY,question=arabConflict.key.integer_id(), text="Palastinians should have their own state, but it should be smaller than the 67 borders imply. Very few settlements should be dismantled.")
        twoStatesPartial.put()
        oneState = Choice(parent=DATASTORE_KEY,question=arabConflict.key.integer_id(), text="Palastinians should become full citizens of Israel.")
        twoStatesPartial.put()

        # UserAnswers
        UserAnswers(parent=DATASTORE_KEY,question=arabConflict.key.integer_id(),user=self.user1.key.integer_id(),choice=twoStates.key.integer_id()).put()
        UserAnswers(parent=DATASTORE_KEY,question=arabConflict.key.integer_id(),user=self.user2.key.integer_id(),choice=twoStatesPartial.key.integer_id()).put()
        UserAnswers(parent=DATASTORE_KEY,question=arabConflict.key.integer_id(),user=self.user3.key.integer_id(),choice=twoStates.key.integer_id()).put()
        UserAnswers(parent=DATASTORE_KEY,question=arabConflict.key.integer_id(),user=self.user4.key.integer_id(),choice=twoStates.key.integer_id()).put()
        

        education = Question(parent=DATASTORE_KEY,poll=poll.key.integer_id(),text="What do you think would be an ideal education policy?",questionType="MultipleChoice")
        education.put()
        singleSystem = Choice(parent=DATASTORE_KEY,question=education.key.integer_id(), text="There should be one, secular, free, education system. Religious studies will have a place in a system of 'sunday schools'. Private education should be disallowed.")
        singleSystem.put()
        independentSystems = Choice(parent=DATASTORE_KEY,question=education.key.integer_id(), text="Independent education streams should be accomodated and funded equally, however they must teach the core corriculum and they must be free to parents")
        independentSystems.put()
        private = Choice(parent=DATASTORE_KEY,question=education.key.integer_id(), text="Schools should be funded equally regardless of core corriculum or the extra cost to parents. Parents will make up their own mind regarding what corriculum fits their kids best and regarding how much money they are willing to spend on education.")

        UserAnswers(parent=DATASTORE_KEY,question=education.key.integer_id(),user=self.user1.key.integer_id(),choice=singleSystem.key.integer_id()).put()
        UserAnswers(parent=DATASTORE_KEY,question=education.key.integer_id(),user=self.user2.key.integer_id(),choice=private.key.integer_id()).put()
        UserAnswers(parent=DATASTORE_KEY,question=education.key.integer_id(),user=self.user3.key.integer_id(),choice=independentSystems.key.integer_id()).put()
        UserAnswers(parent=DATASTORE_KEY,question=education.key.integer_id(),user=self.user4.key.integer_id(),choice=singleSystem.key.integer_id()).put()

    def addPublicTransportationPoll(self):
        poll = Poll(parent=DATASTORE_KEY,title="Public Transit on Saturdays")
        poll.put()

        question1 = Question(parent=DATASTORE_KEY,poll=poll.key.integer_id(),text="Should there be public transportation on Saturdays?",questionType="MultipleChoice")
        question1.put()
        question2 = Question(parent=DATASTORE_KEY,poll=poll.key.integer_id(),text="Should local municipalities be allowed to decide independently?",questionType="MultipleChoice")
        question2.put()

        # Yes/No choices
        choice1yes = Choice(parent=DATASTORE_KEY,question=question1.key.integer_id(), text="Yes")
        choice1yes.put()
        choice1no = Choice(parent=DATASTORE_KEY,question=question1.key.integer_id(), text="No")
        choice1no.put()
        choice2yes = Choice(parent=DATASTORE_KEY,question=question2.key.integer_id(), text="Yes")
        choice2yes.put()
        choice2no = Choice(parent=DATASTORE_KEY,question=question2.key.integer_id(), text="No")
        choice2no.put()

        # UserAnswers
        UserAnswers(parent=DATASTORE_KEY,question=question1.key.integer_id(),user=self.user1.key.integer_id(),choice=choice1yes.key.integer_id()).put()
        UserAnswers(parent=DATASTORE_KEY,question=question2.key.integer_id(),user=self.user1.key.integer_id(),choice=choice2yes.key.integer_id()).put()
        UserAnswers(parent=DATASTORE_KEY,question=question1.key.integer_id(),user=self.user2.key.integer_id(),choice=choice1yes.key.integer_id()).put()
        UserAnswers(parent=DATASTORE_KEY,question=question2.key.integer_id(),user=self.user2.key.integer_id(),choice=choice2yes.key.integer_id()).put()
        UserAnswers(parent=DATASTORE_KEY,question=question1.key.integer_id(),user=self.user3.key.integer_id(),choice=choice1yes.key.integer_id()).put()
        UserAnswers(parent=DATASTORE_KEY,question=question2.key.integer_id(),user=self.user3.key.integer_id(),choice=choice2yes.key.integer_id()).put()
        UserAnswers(parent=DATASTORE_KEY,question=question1.key.integer_id(),user=self.user4.key.integer_id(),choice=choice1no.key.integer_id()).put()
        UserAnswers(parent=DATASTORE_KEY,question=question2.key.integer_id(),user=self.user4.key.integer_id(),choice=choice2yes.key.integer_id()).put()
        






