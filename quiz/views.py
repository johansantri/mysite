import random
from django.shortcuts import render,redirect
from .models import Question, Choice, Score
from django.http import JsonResponse
from .models import AttemptedQuestion
from datetime import datetime, timedelta
SUBMISSION_LIMIT = 1
QUIZ_TIME_LIMIT = timedelta(minutes=1)

def quiz_view(request):
    if request.user.is_authenticated:
        user_identifier = request.user.username
    else:
        user_identifier = f"Anonymous-{request.session.session_key}"

    # Check if the user has already submitted
    if Score.objects.filter(user=user_identifier, submitted=True).exists():
        return render(request, 'quiz/limit_reached.html', {
            'message': "You have already submitted the quiz.",
        })

    # Initialize session data for new users
    if 'question_ids' not in request.session or not request.session['question_ids']:
        questions = list(Question.objects.values_list('id', flat=True))
        random.shuffle(questions)
        request.session['question_ids'] = questions
        request.session['quiz_start_time'] = datetime.now().isoformat()

    question_ids = request.session['question_ids']
    questions = Question.objects.filter(id__in=question_ids[:5])

    return render(request, 'quiz/quiz.html', {
        'questions': questions,
        'time_limit': QUIZ_TIME_LIMIT.total_seconds(),
    })





def check_answer(request, question_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    question_ids = request.session.get('question_ids', [])
    if question_id not in question_ids:
        return JsonResponse({'error': 'Invalid question'}, status=400)

    try:
        question = Question.objects.get(id=question_id)
        selected_choice_id = request.POST.get('choice')
        selected_choice = question.choices.get(id=selected_choice_id)
        is_correct = selected_choice.is_correct
    except (Question.DoesNotExist, Choice.DoesNotExist, TypeError):
        return JsonResponse({'error': 'Invalid choice or question'}, status=400)
    
    # Save the attempt to the history
    if request.user.is_authenticated:
        user = request.user.username
    else:
        user = f"Anonymous-{request.session.session_key}"

    AttemptedQuestion.objects.create(
        user=user,
        question=question,
        selected_choice=selected_choice,
        is_correct=is_correct,
    )

    is_correct = selected_choice.is_correct

    # Initialize session data if not present
    request.session.setdefault('score', 0)
    request.session.setdefault('answered_questions', [])

    answered_questions = set(request.session['answered_questions'])

    if question_id not in answered_questions:
        if is_correct:
            request.session['score'] += 1
        answered_questions.add(question_id)

    request.session['answered_questions'] = list(answered_questions)
    request.session.modified = True

    return render(request, 'quiz/answer.html', {
        'is_correct': is_correct,
        'correct_choice': question.choices.filter(is_correct=True).first(),
    })

def restart_quiz(request):
    # Clear session data
    request.session.pop('score', None)
    request.session.pop('answered_questions', None)
    request.session.pop('question_ids', None)

    # Shuffle and reassign new questions
    questions = list(Question.objects.values_list('id', flat=True))
    random.shuffle(questions)
    request.session['question_ids'] = questions

    return redirect('quiz')





def score_list(request):
    scores = Score.objects.all().order_by('-date')  # Show recent scores first
    return render(request, 'quiz/scores.html', {'scores': scores})


def calculate_grade(score, total_questions):
    if total_questions == 0:
        return "N/A"  # Avoid division by zero
    percentage = (score / total_questions) * 100
    grade_thresholds = [
        (90, "A"),
        (80, "B"),
        (70, "C"),
        (60, "D"),
    ]
    for threshold, grade in grade_thresholds:
        if percentage >= threshold:
            return grade
    return "F"


def quiz_result(request):
    if request.method == 'POST':
        if request.user.is_authenticated:
            user_identifier = request.user.username
        else:
            user_identifier = f"Anonymous-{request.session.session_key}"

        # Check if the user has already submitted
        if Score.objects.filter(user=user_identifier, submitted=True).exists():
            return render(request, 'quiz/limit_reached.html', {
                'message': "You have already submitted the quiz.",
            })

        # Check if the time limit has been exceeded
        start_time = request.session.get('quiz_start_time')
        if not start_time:
            return render(request, 'quiz/error.html', {
                'message': 'Quiz start time not found.'
            })

        start_time = datetime.fromisoformat(start_time)
        time_taken = datetime.now() - start_time

        if time_taken > QUIZ_TIME_LIMIT:
            Score.objects.create(
                user=user_identifier,
                score=0,
                total_questions=0,
                grade="F",
                submitted=True
            )
            return render(request, 'quiz/limit_reached.html', {
                'message': "Time limit exceeded! You cannot submit the quiz.",
            })

        # Process the quiz answers
        score = 0
        answered_questions = []
        total_questions = 0

        for key, value in request.POST.items():
            if key.startswith('question_'):
                question_id = key.split('_')[1]
                try:
                    question = Question.objects.get(id=question_id)
                    selected_choice = question.choices.get(id=value)
                    is_correct = selected_choice.is_correct

                    AttemptedQuestion.objects.create(
                        user=user_identifier,
                        question=question,
                        selected_choice=selected_choice,
                        is_correct=is_correct
                    )

                    total_questions += 1
                    answered_questions.append(int(question_id))
                    if is_correct:
                        score += 1
                except (Question.DoesNotExist, Choice.DoesNotExist, ValueError):
                    continue

        grade = calculate_grade(score, total_questions)

        Score.objects.create(
            user=user_identifier,
            score=score,
            total_questions=total_questions,
            grade=grade,
            submitted=True
        )

        request.session['has_submitted'] = True
        return render(request, 'quiz/result.html', {
            'score': score,
            'total_questions': total_questions,
            'grade': grade,
        })

    return JsonResponse({'error': 'Invalid request method'}, status=405)

def question_history(request):
    if request.user.is_authenticated:
        user = request.user.username
    else:
        user = f"Anonymous-{request.session.session_key}"

    history = AttemptedQuestion.objects.filter(user=user).order_by('-date_attempted')
    return render(request, 'quiz/history.html', {'history': history})


