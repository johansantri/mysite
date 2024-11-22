import random
from django.shortcuts import render,redirect
from .models import Question, Choice, Score
from django.http import JsonResponse

def quiz_view(request):
    if 'question_ids' not in request.session:
        # Shuffle and store question IDs in the session
        questions = list(Question.objects.values_list('id', flat=True))
        random.shuffle(questions)
        request.session['question_ids'] = questions

    # Retrieve questions based on IDs in the session
    question_ids = request.session['question_ids']
    questions = Question.objects.filter(id__in=question_ids[:5])  # Limit to 5 questions

    return render(request, 'quiz/quiz.html', {'questions': questions})


def check_answer(request, question_id):
    question_ids = request.session.get('question_ids', [])
    if question_id not in question_ids:
        return JsonResponse({'error': 'Invalid question'}, status=400)

    question = Question.objects.get(id=question_id)
    selected_choice_id = request.POST.get('choice')
    selected_choice = question.choices.get(id=selected_choice_id)
    is_correct = selected_choice.is_correct

    # Session logic remains the same as before
    if 'score' not in request.session:
        request.session['score'] = 0
        request.session['answered_questions'] = []

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
    request.session['score'] = 0
    request.session['answered_questions'] = []
    request.session['question_ids'] = []
    return redirect('quiz')




def score_list(request):
    scores = Score.objects.all().order_by('-date')  # Show recent scores first
    return render(request, 'quiz/scores.html', {'scores': scores})


def calculate_grade(score, total_questions):
    if total_questions == 0:
        return "N/A"  # Handle edge case where no questions exist
    percentage = (score / total_questions) * 100
    if percentage >= 90:
        return "A"
    elif percentage >= 80:
        return "B"
    elif percentage >= 70:
        return "C"
    elif percentage >= 60:
        return "D"
    else:
        return "F"

def quiz_result(request):
    score = request.session.get('score', 0)
    total_questions = Question.objects.count()

    # Calculate the grade
    grade = calculate_grade(score, total_questions)

    # Save the score and grade to the database
    Score.objects.create(
        user=request.user.username if request.user.is_authenticated else "Anonymous",
        score=score,
        total_questions=total_questions,
        grade=grade,
    )

    # Clear session data
    request.session['score'] = 0
    request.session['answered_questions'] = []

    return render(request, 'quiz/result.html', {
        'score': score,
        'total_questions': total_questions,
        'grade': grade,
    })

