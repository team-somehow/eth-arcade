import { initializeApp } from 'firebase/app';
import { getFirestore, doc, setDoc, serverTimestamp } from 'firebase/firestore/lite';

const app = initializeApp({
  projectId: 'personal-projects-e8a07',
  appId: '1:873434627474:web:34a83747c2f1a6cfcf954b',
  apiKey: 'AIzaSyBxBxQxYJioSKJpoeF1wC9Co1gbKdt7jnc',
}, 'eth-arcade-signups');
const db = getFirestore(app);

export async function saveSignup(email: string, quantity: number, reference: string) {
  await setDoc(doc(db, 'ethArcadeSignups', reference), {
    email: email.trim().toLowerCase(), quantity, reference,
    source: 'eth-arcade-website', createdAt: serverTimestamp(),
  });
}
