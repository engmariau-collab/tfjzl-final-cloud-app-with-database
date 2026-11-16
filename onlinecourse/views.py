from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from .models import Course, Enrollment, Submission, Choice

import logging

logger = logging.getLogger(__name__)


# Registration
def registration_request(request):
    context = {}

    if request.method == 'GET':
        return render(
            request,
            'onlinecourse/user_registration_bootstrap.html',
            context
        )

    elif request.method == 'POST':

        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']

        user_exist = User.objects.filter(username=username).exists()

        if not user_exist:

            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                password=password
            )

            login(request, user)

            return redirect("onlinecourse:index")

        else:
            context['message'] = "User already exists."

            return render(
                request,
                'onlinecourse/user_registration_bootstrap.html',
                context
            )


# Login
def login_request(request):

    context = {}

    if request.method == "POST":

        username = request.POST['username']
        password = request.POST['psw']

        user = authenticate(
            username=username,
            password=password
        )

        if user is not None:

            login(request, user)

            return redirect('onlinecourse:index')

        else:

            context['message'] = "Invalid username or password."

            return render(
                request,
                'onlinecourse/user_login_bootstrap.html',
                context
            )

    else:

        return render(
            request,
            'onlinecourse/user_login_bootstrap.html',
            context
        )


# Logout
def logout_request(request):

    logout(request)

    return redirect('onlinecourse:index')


# Check Enrollment
def check_if_enrolled(user, course):

    is_enrolled = False

    if user.is_authenticated:

        num_results = Enrollment.objects.filter(
            user=user,
            course=course
        ).count()

        if num_results > 0:
            is_enrolled = True

    return is_enrolled


# Course List
class CourseListView(generic.ListView):

    template_name = 'onlinecourse/course_list_bootstrap.html'

    context_object_name = 'course_list'

    def get_queryset(self):

        user = self.request.user

        courses = Course.objects.order_by(
            '-total_enrollment'
        )[:10]

        for course in courses:

            if user.is_authenticated:

                course.is_enrolled = check_if_enrolled(
                    user,
                    course
                )

            else:

                course.is_enrolled = False

        return courses


# Course Details
class CourseDetailView(generic.DetailView):

    model = Course

    template_name = 'onlinecourse/course_detail_bootstrap.html'

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        course = self.object

        user = self.request.user

        if user.is_authenticated:

            course.is_enrolled = check_if_enrolled(
                user,
                course
            )

        else:

            course.is_enrolled = False

        return context


# Enroll Course
@login_required
def enroll(request, course_id):

    course = get_object_or_404(
        Course,
        pk=course_id
    )

    user = request.user

    is_enrolled = check_if_enrolled(
        user,
        course
    )

    if not is_enrolled:

        Enrollment.objects.create(
            user=user,
            course=course,
            mode='honor'
        )

        course.total_enrollment += 1

        course.save()

    return HttpResponseRedirect(
        reverse(
            viewname='onlinecourse:course_details',
            args=(course.id,)
        )
    )


# Extract Exam Answers
def extract_answers(request):

    submitted_answers = []

    for key in request.POST:

        if key.startswith('choice'):

            try:

                value = int(request.POST[key])

                submitted_answers.append(value)

            except (ValueError, TypeError):

                continue

    return submitted_answers


# TASK 5 - Submit Exam
@login_required
@require_POST
def submit(request, course_id):

    course = get_object_or_404(
        Course,
        pk=course_id
    )

    user = request.user

    # Get student enrollment
    enrollment = get_object_or_404(
        Enrollment,
        user=user,
        course=course
    )

    # Create submission
    submission = Submission.objects.create(
        enrollment=enrollment
    )

    # Collect selected answers
    submitted_answers = extract_answers(request)

    # Only accept choices belonging to this course
    selected_choices = Choice.objects.filter(
        id__in=submitted_answers,
        question__course=course
    )

    # Save selected choices
    submission.choices.set(selected_choices)

    # Redirect to exam result
    return redirect(
        'onlinecourse:show_exam_result',
        course_id=course.id,
        submission_id=submission.id
    )


# TASK 5 - Show Exam Result
@login_required
def show_exam_result(request, course_id, submission_id):

    course = get_object_or_404(
        Course,
        pk=course_id
    )

    # Get submission belonging to current student and course
    submission = get_object_or_404(
        Submission,
        pk=submission_id,
        enrollment__user=request.user,
        enrollment__course=course
    )

    # Get selected choices
    selected_choices = submission.choices.all()

    selected_ids = list(
        selected_choices.values_list('id', flat=True)
    )

    # Calculate result
    total_score = 0
    grade = 0

    question_results = []

    for question in course.question_set.all():

        question_choices = question.choice_set.all()

        correct_choices = question_choices.filter(
            is_correct=True
        )

        selected_for_question = question_choices.filter(
            id__in=selected_ids
        )

        # Check whether selected answers are correct
        correct_ids = set(
            correct_choices.values_list('id', flat=True)
        )

        selected_question_ids = set(
            selected_for_question.values_list('id', flat=True)
        )

        is_correct = (
            correct_ids == selected_question_ids
            and len(correct_ids) > 0
        )

        # Calculate grade
        total_score += question.grade

        if is_correct:
            grade += question.grade

        question_results.append({

            'question': question,

            'choices': question_choices,

            'selected_choices': selected_for_question,

            'correct_choices': correct_choices,

            'is_correct': is_correct,

            'grade': question.grade if is_correct else 0

        })

    # Result context
    context = {

        'course': course,

        'submission': submission,

        'question_results': question_results,

        'grade': grade,

        'total_score': total_score,

        'selected_choices': selected_choices,

    }

    return render(
        request,
        'onlinecourse/exam_result_bootstrap.html',
        context
    )
